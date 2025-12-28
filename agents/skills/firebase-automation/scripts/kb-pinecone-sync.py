#!/usr/bin/env python3
"""
Knowledge Base Pinecone Sync for ProCaffe Second Brain.

Syncs Firestore content to Pinecone vector database for semantic search.

Usage:
    python3 kb-pinecone-sync.py                    # Sync all fb_posts
    python3 kb-pinecone-sync.py --limit 10        # Sync first 10 posts
    python3 kb-pinecone-sync.py --dry-run         # Show what would be done
    python3 kb-pinecone-sync.py --namespace tiktok # Sync specific namespace

Requirements:
    - PINECONE_API_KEY in config.py or env var
    - GEMINI_API_KEY in .env or config.py or env var
    - firebase_service_account.json in project root
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Load .env file if present
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
for env_file in [PROJECT_DIR / ".env", PROJECT_DIR / ".env.local"]:
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

import firebase_admin
import google.generativeai as genai
from firebase_admin import credentials, firestore
from pinecone import Pinecone, ServerlessSpec

from config import (
    FIREBASE_SERVICE_ACCOUNT,
    FIREBASE_PROJECT_ID,
    DATA_DIR,
    RATE_LIMIT_DELAY,
)

# Pinecone Configuration
PINECONE_INDEX_NAME = "procaffe-kb"
PINECONE_DIMENSION = 768  # Gemini text-embedding-004
PINECONE_METRIC = "cosine"
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"  # Pinecone Starter tier default

# Namespaces for logical separation
NAMESPACES = ["facebook", "tiktok", "products", "leads", "faqs"]

# Batch size for Pinecone upserts
BATCH_SIZE = 100

# Global instances
_firebase_app = None
_pinecone_client = None
_pinecone_index = None


def get_pinecone_api_key() -> str:
    """Get Pinecone API key from env or config."""
    api_key = os.environ.get("PINECONE_API_KEY")
    if api_key:
        return api_key
    # Check if defined in config (we'll add this later)
    try:
        from config import PINECONE_API_KEY
        return PINECONE_API_KEY
    except ImportError:
        pass
    print("ERROR: PINECONE_API_KEY not found")
    print("Set it via: export PINECONE_API_KEY=your-key")
    sys.exit(1)


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app is not None:
        return firestore.client()

    if not FIREBASE_SERVICE_ACCOUNT.exists():
        print(f"ERROR: Service account not found: {FIREBASE_SERVICE_ACCOUNT}")
        sys.exit(1)

    cred = credentials.Certificate(str(FIREBASE_SERVICE_ACCOUNT))
    _firebase_app = firebase_admin.initialize_app(cred, {
        'projectId': FIREBASE_PROJECT_ID,
    })
    return firestore.client()


def initialize_pinecone(dry_run: bool = False):
    """Initialize Pinecone client and index."""
    global _pinecone_client, _pinecone_index

    if _pinecone_index is not None:
        return _pinecone_index

    api_key = get_pinecone_api_key()
    _pinecone_client = Pinecone(api_key=api_key)

    # Check if index exists
    existing_indexes = [idx.name for idx in _pinecone_client.list_indexes()]

    if PINECONE_INDEX_NAME not in existing_indexes:
        if dry_run:
            print(f"[DRY RUN] Would create index: {PINECONE_INDEX_NAME}")
            return None
        print(f"Creating index: {PINECONE_INDEX_NAME}...")
        _pinecone_client.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=PINECONE_DIMENSION,
            metric=PINECONE_METRIC,
            spec=ServerlessSpec(
                cloud=PINECONE_CLOUD,
                region=PINECONE_REGION
            )
        )
        # Wait for index to be ready
        print("Waiting for index to be ready...")
        time.sleep(10)

    _pinecone_index = _pinecone_client.Index(PINECONE_INDEX_NAME)
    return _pinecone_index


def initialize_gemini():
    """Initialize Gemini for embeddings."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found")
        print("Set it via: export GEMINI_API_KEY=your-key")
        sys.exit(1)
    genai.configure(api_key=api_key)


def embed_text(text: str) -> list[float]:
    """Generate 768-dim embedding using Gemini."""
    if not text or len(text.strip()) == 0:
        text = "empty content"

    # Truncate to avoid token limits (roughly 8k tokens)
    max_chars = 25000
    if len(text) > max_chars:
        text = text[:max_chars]

    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document"
    )
    return result["embedding"]


def load_sync_progress(namespace: str) -> set:
    """Load synced IDs for a namespace."""
    progress_file = DATA_DIR / f"pinecone-sync-{namespace}.json"
    if progress_file.exists():
        with open(progress_file, "r") as f:
            data = json.load(f)
            return set(data.get("synced_ids", []))
    return set()


def save_sync_progress(namespace: str, synced_ids: set):
    """Save synced IDs for a namespace."""
    progress_file = DATA_DIR / f"pinecone-sync-{namespace}.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(progress_file, "w") as f:
        json.dump({
            "namespace": namespace,
            "synced_ids": list(synced_ids),
            "last_sync": datetime.now().isoformat(),
            "count": len(synced_ids)
        }, f, indent=2)


def prepare_faq_for_embedding(faq: dict) -> tuple[str, dict]:
    """Prepare FAQ text and metadata for embedding."""
    question = faq.get("question", "") or ""
    answer = faq.get("answer", "") or ""
    category = faq.get("category", "general") or "general"

    # Combine Q+A for better semantic search
    text = f"Câu hỏi: {question}\nTrả lời: {answer}"

    # Metadata for filtering
    metadata = {
        "source": "faq",
        "content_type": "faq",
        "category": category,
        "text_preview": f"Q: {question[:100]}... A: {answer[:100]}...",
        "question": question[:200],
        "language": "vi",
    }

    return text, metadata


def prepare_product_for_embedding(product: dict) -> tuple[str, dict]:
    """Prepare product text and metadata for embedding."""
    name = product.get("name", "") or ""
    brand = product.get("brand", "") or ""
    description = product.get("description", "") or ""
    features = product.get("features", "") or ""
    product_type = product.get("type", "") or ""
    price = product.get("price_vnd", 0) or 0
    price_promo = product.get("price_promo_vnd", 0) or 0
    warranty = product.get("warranty_months", 12) or 12

    # Format price for display
    price_display = f"{price_promo:,}đ" if price_promo else f"{price:,}đ"

    # Create searchable text with context
    text = f"Sản phẩm: {name}. Thương hiệu: {brand}. {description}. Giá: {price_display}. Tính năng: {features}. Bảo hành: {warranty} tháng."

    # Metadata for filtering
    metadata = {
        "source": "product",
        "content_type": "product",
        "category": product_type,
        "brand": brand,
        "price": price_promo or price,
        "warranty_months": warranty,
        "text_preview": text[:300],
        "language": "vi",
    }

    return text, metadata


def sync_products_to_pinecone(db, index, limit: int = None, dry_run: bool = False) -> int:
    """Sync Firestore products to Pinecone products namespace."""
    namespace = "products"
    print(f"\n{'='*60}")
    print(f"Syncing {namespace} namespace")
    print(f"{'='*60}")

    # Load progress
    synced_ids = load_sync_progress(namespace)
    print(f"Previously synced: {len(synced_ids)} documents")

    # Fetch products from Firestore
    query = db.collection("products")
    if limit:
        query = query.limit(limit)

    products = list(query.stream())
    print(f"Found {len(products)} products in Firestore")

    # Filter out already synced
    to_sync = []
    for product in products:
        doc_id = product.id
        if doc_id not in synced_ids:
            to_sync.append(product)

    print(f"New products to sync: {len(to_sync)}")

    if not to_sync:
        print("Nothing to sync")
        return 0

    # Process in batches
    vectors = []
    synced_count = 0

    for i, product in enumerate(to_sync):
        doc_id = product.id
        data = product.to_dict()

        print(f"  [{i+1}/{len(to_sync)}] Processing: {doc_id}")

        # Prepare text and metadata
        text, metadata = prepare_product_for_embedding(data)

        if dry_run:
            print(f"    [DRY RUN] Would embed: {text[:50]}...")
            synced_ids.add(doc_id)
            synced_count += 1
            continue

        try:
            # Generate embedding
            embedding = embed_text(text)

            # Add to batch
            vectors.append({
                "id": doc_id,
                "values": embedding,
                "metadata": metadata
            })

            # Rate limit for Gemini
            time.sleep(RATE_LIMIT_DELAY)

            # Upsert when batch full
            if len(vectors) >= BATCH_SIZE:
                print(f"    Upserting batch of {len(vectors)} vectors...")
                index.upsert(vectors=vectors, namespace=namespace)
                for v in vectors:
                    synced_ids.add(v["id"])
                synced_count += len(vectors)
                vectors = []
                save_sync_progress(namespace, synced_ids)

        except Exception as e:
            print(f"    [ERROR] Failed: {e}")
            continue

    # Final batch
    if vectors and not dry_run:
        print(f"    Upserting final batch of {len(vectors)} vectors...")
        index.upsert(vectors=vectors, namespace=namespace)
        for v in vectors:
            synced_ids.add(v["id"])
        synced_count += len(vectors)

    # Save progress
    if not dry_run:
        save_sync_progress(namespace, synced_ids)

    return synced_count


def sync_faqs_to_pinecone(db, index, limit: int = None, dry_run: bool = False) -> int:
    """Sync Firestore faqs to Pinecone faqs namespace."""
    namespace = "faqs"
    print(f"\n{'='*60}")
    print(f"Syncing {namespace} namespace")
    print(f"{'='*60}")

    # Load progress
    synced_ids = load_sync_progress(namespace)
    print(f"Previously synced: {len(synced_ids)} documents")

    # Fetch FAQs from Firestore
    query = db.collection("faqs")
    if limit:
        query = query.limit(limit)

    faqs = list(query.stream())
    print(f"Found {len(faqs)} FAQs in Firestore")

    # Filter out already synced
    to_sync = []
    for faq in faqs:
        doc_id = faq.id
        if doc_id not in synced_ids:
            to_sync.append(faq)

    print(f"New FAQs to sync: {len(to_sync)}")

    if not to_sync:
        print("Nothing to sync")
        return 0

    # Process in batches
    vectors = []
    synced_count = 0

    for i, faq in enumerate(to_sync):
        doc_id = faq.id
        data = faq.to_dict()

        print(f"  [{i+1}/{len(to_sync)}] Processing: {doc_id}")

        # Prepare text and metadata
        text, metadata = prepare_faq_for_embedding(data)

        if dry_run:
            print(f"    [DRY RUN] Would embed: {text[:50]}...")
            synced_ids.add(doc_id)
            synced_count += 1
            continue

        try:
            # Generate embedding
            embedding = embed_text(text)

            # Add to batch
            vectors.append({
                "id": doc_id,
                "values": embedding,
                "metadata": metadata
            })

            # Rate limit for Gemini
            time.sleep(RATE_LIMIT_DELAY)

            # Upsert when batch full
            if len(vectors) >= BATCH_SIZE:
                print(f"    Upserting batch of {len(vectors)} vectors...")
                index.upsert(vectors=vectors, namespace=namespace)
                for v in vectors:
                    synced_ids.add(v["id"])
                synced_count += len(vectors)
                vectors = []
                save_sync_progress(namespace, synced_ids)

        except Exception as e:
            print(f"    [ERROR] Failed: {e}")
            continue

    # Final batch
    if vectors and not dry_run:
        print(f"    Upserting final batch of {len(vectors)} vectors...")
        index.upsert(vectors=vectors, namespace=namespace)
        for v in vectors:
            synced_ids.add(v["id"])
        synced_count += len(vectors)

    # Save progress
    if not dry_run:
        save_sync_progress(namespace, synced_ids)

    return synced_count


def prepare_fb_post_for_embedding(post: dict) -> tuple[str, dict]:
    """Prepare FB post text and metadata for embedding."""
    # Combine text fields for embedding
    content = post.get("content", "") or ""
    post_type = post.get("type", "status")

    # Create searchable text
    text = f"{content} {post_type}"

    # Calculate engagement score
    stats = post.get("stats", {})
    engagement = sum([
        stats.get("likes", 0),
        stats.get("shares", 0) * 2,  # shares worth more
        stats.get("comments", 0) * 1.5
    ])

    # Metadata for filtering
    metadata = {
        "source": "facebook",
        "content_type": post_type,
        "text_preview": content[:200] if content else "",
        "engagement": int(engagement),
        "published_at": post.get("publishedAt", ""),
        "language": "vi",  # Assume Vietnamese
    }

    return text, metadata


def sync_fb_posts_to_pinecone(db, index, limit: int = None, dry_run: bool = False) -> int:
    """Sync Firestore fb_posts to Pinecone facebook namespace."""
    namespace = "facebook"
    print(f"\n{'='*60}")
    print(f"Syncing {namespace} namespace")
    print(f"{'='*60}")

    # Load progress
    synced_ids = load_sync_progress(namespace)
    print(f"Previously synced: {len(synced_ids)} documents")

    # Fetch posts from Firestore
    query = db.collection("fb_posts")
    if limit:
        query = query.limit(limit)

    posts = list(query.stream())
    print(f"Found {len(posts)} posts in Firestore")

    # Filter out already synced
    to_sync = []
    for post in posts:
        doc_id = post.id
        if doc_id not in synced_ids:
            to_sync.append(post)

    print(f"New posts to sync: {len(to_sync)}")

    if not to_sync:
        print("Nothing to sync")
        return 0

    # Process in batches
    vectors = []
    synced_count = 0

    for i, post in enumerate(to_sync):
        doc_id = post.id
        data = post.to_dict()

        print(f"  [{i+1}/{len(to_sync)}] Processing: {doc_id}")

        # Prepare text and metadata
        text, metadata = prepare_fb_post_for_embedding(data)

        if dry_run:
            print(f"    [DRY RUN] Would embed: {text[:50]}...")
            synced_ids.add(doc_id)
            synced_count += 1
            continue

        try:
            # Generate embedding
            embedding = embed_text(text)

            # Add to batch
            vectors.append({
                "id": doc_id,
                "values": embedding,
                "metadata": metadata
            })

            # Rate limit for Gemini
            time.sleep(RATE_LIMIT_DELAY)

            # Upsert when batch full
            if len(vectors) >= BATCH_SIZE:
                print(f"    Upserting batch of {len(vectors)} vectors...")
                index.upsert(vectors=vectors, namespace=namespace)
                for v in vectors:
                    synced_ids.add(v["id"])
                synced_count += len(vectors)
                vectors = []
                save_sync_progress(namespace, synced_ids)

        except Exception as e:
            print(f"    [ERROR] Failed: {e}")
            continue

    # Final batch
    if vectors and not dry_run:
        print(f"    Upserting final batch of {len(vectors)} vectors...")
        index.upsert(vectors=vectors, namespace=namespace)
        for v in vectors:
            synced_ids.add(v["id"])
        synced_count += len(vectors)

    # Save progress
    if not dry_run:
        save_sync_progress(namespace, synced_ids)

    return synced_count


def get_index_stats(index) -> dict:
    """Get Pinecone index statistics."""
    if index is None:
        return {}
    stats = index.describe_index_stats()
    return stats.to_dict() if hasattr(stats, 'to_dict') else stats


def main():
    parser = argparse.ArgumentParser(description="Pinecone Sync for ProCaffe KB")
    parser.add_argument("--limit", type=int, help="Limit documents to sync")
    parser.add_argument("--namespace", type=str, choices=NAMESPACES,
                        default="facebook", help="Namespace to sync")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--stats", action="store_true", help="Show index stats only")
    args = parser.parse_args()

    print("="*60)
    print("ProCaffe Knowledge Base - Pinecone Sync")
    print("="*60)

    # Initialize services
    if not args.dry_run:
        initialize_gemini()

    db = initialize_firebase()
    index = initialize_pinecone(args.dry_run)

    # Stats only mode
    if args.stats:
        stats = get_index_stats(index)
        print(f"\nIndex Stats:")
        print(json.dumps(stats, indent=2))
        return

    # Sync based on namespace
    if args.namespace == "facebook":
        count = sync_fb_posts_to_pinecone(db, index, args.limit, args.dry_run)
    elif args.namespace == "faqs":
        count = sync_faqs_to_pinecone(db, index, args.limit, args.dry_run)
    elif args.namespace == "products":
        count = sync_products_to_pinecone(db, index, args.limit, args.dry_run)
    else:
        print(f"Namespace '{args.namespace}' sync not implemented yet")
        count = 0

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Documents synced: {count}")

    if not args.dry_run and index:
        stats = get_index_stats(index)
        print(f"\nIndex Stats:")
        print(json.dumps(stats, indent=2))
    elif args.dry_run:
        print("\n[DRY RUN] No changes made")


if __name__ == "__main__":
    main()
