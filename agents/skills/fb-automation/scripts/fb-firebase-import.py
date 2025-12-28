#!/usr/bin/env python3
"""
Firebase Importer for ProCaffe Facebook Content.

Uploads scraped media to Firebase Storage and indexes posts in Firestore.

Usage:
    python3 fb-firebase-import.py                   # Full import
    python3 fb-firebase-import.py --limit 10       # Import first 10 posts
    python3 fb-firebase-import.py --dry-run        # Show what would be done
    python3 fb-firebase-import.py --skip-upload    # Skip media upload, only Firestore

Requirements:
    - firebase_service_account.json in project root
    - data/fb-posts.json from fb-scrape-content.py
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

from config import (
    FIREBASE_SERVICE_ACCOUNT,
    FIREBASE_PROJECT_ID,
    FIREBASE_STORAGE_BUCKET,
    FB_POSTS_FILE,
    FB_IMPORT_PROGRESS_FILE,
    DATA_DIR,
)

# Global Firebase app
_app = None


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    global _app
    if _app is not None:
        return _app

    if not FIREBASE_SERVICE_ACCOUNT.exists():
        print(f"ERROR: Service account not found: {FIREBASE_SERVICE_ACCOUNT}")
        sys.exit(1)

    cred = credentials.Certificate(str(FIREBASE_SERVICE_ACCOUNT))
    _app = firebase_admin.initialize_app(cred, {
        'projectId': FIREBASE_PROJECT_ID,
        'storageBucket': FIREBASE_STORAGE_BUCKET,
    })
    return _app


def load_progress() -> dict:
    """Load import progress from file."""
    if FB_IMPORT_PROGRESS_FILE.exists():
        with open(FB_IMPORT_PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"importedPosts": [], "uploadedMedia": []}


def save_progress(progress: dict):
    """Save import progress to file."""
    FB_IMPORT_PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FB_IMPORT_PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def upload_media(media: dict, progress: dict, dry_run: bool = False) -> dict:
    """Upload media file to Firebase Storage. Returns updated media dict."""
    local_path = Path(media.get("localPath", ""))

    if not local_path.exists():
        print(f"    [SKIP] File not found: {local_path}")
        return media

    md5 = media.get("md5", local_path.stem)

    # Storage path: fb/videos/{md5}.mp4 or fb/images/{md5}.jpg
    media_type = media.get("type", "image")
    folder = "videos" if media_type == "video" else "images"
    ext = local_path.suffix or (".mp4" if media_type == "video" else ".jpg")
    storage_path = f"fb/{folder}/{md5}{ext}"

    # Check if already uploaded
    if storage_path in progress.get("uploadedMedia", []):
        print(f"    [SKIP] Already uploaded: {storage_path}")
        media["storagePath"] = storage_path
        return media

    if dry_run:
        print(f"    [DRY RUN] Would upload: {local_path.name} -> {storage_path}")
        media["storagePath"] = storage_path
        return media

    try:
        bucket = storage.bucket()
        blob = bucket.blob(storage_path)

        # Check if blob exists
        if blob.exists():
            print(f"    [EXIST] {storage_path}")
        else:
            # Set content type
            content_type = "video/mp4" if media_type == "video" else "image/jpeg"
            blob.upload_from_filename(str(local_path), content_type=content_type)
            print(f"    [UPLOAD] {storage_path}")

        # Make public and get URL
        blob.make_public()
        media["storagePath"] = storage_path
        media["url"] = blob.public_url

        progress["uploadedMedia"].append(storage_path)
        return media

    except Exception as e:
        print(f"    [ERROR] Upload failed: {e}")
        return media


def import_comments(post_id: str, comments: list, db, dry_run: bool = False) -> int:
    """Import comments as subcollection. Returns count imported."""
    if not comments:
        return 0

    if dry_run:
        total = sum(1 + len(c.get("replies", [])) for c in comments)
        print(f"    [DRY RUN] Would import {total} comments")
        return total

    # Get subcollection reference
    comments_ref = db.collection("fb_posts").document(post_id).collection("comments")

    count = 0
    batch = db.batch()
    batch_count = 0

    for comment in comments:
        # Import main comment
        comment_id = f"comment_{comment.get('id', '')}"
        comment_doc = {
            "id": comment_id,
            "author": comment.get("author", {}),
            "text": comment.get("text", ""),
            "createdAt": comment.get("createdAt", ""),
            "likes": comment.get("likes", 0),
            "parentId": None
        }
        batch.set(comments_ref.document(comment_id), comment_doc)
        count += 1
        batch_count += 1

        # Import replies
        for reply in comment.get("replies", []):
            reply_id = f"comment_{reply.get('id', '')}"
            reply_doc = {
                "id": reply_id,
                "author": reply.get("author", {}),
                "text": reply.get("text", ""),
                "createdAt": reply.get("createdAt", ""),
                "likes": reply.get("likes", 0),
                "parentId": comment_id
            }
            batch.set(comments_ref.document(reply_id), reply_doc)
            count += 1
            batch_count += 1

        # Firestore batch limit is 500
        if batch_count >= 450:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    # Commit remaining
    if batch_count > 0:
        batch.commit()

    print(f"    [COMMENTS] Imported {count} comments")
    return count


def import_post(post: dict, progress: dict, db, skip_upload: bool = False, dry_run: bool = False) -> bool:
    """Import single post to Firestore. Returns True if successful."""
    post_id = f"fb_{post.get('id', '')}"

    # Check if already imported
    if post_id in progress.get("importedPosts", []):
        print(f"  [SKIP] Already imported: {post_id}")
        return True

    print(f"  Importing: {post_id}")

    # Upload media first
    uploaded_media = []
    if not skip_upload:
        for media in post.get("media", []):
            updated_media = upload_media(media, progress, dry_run)
            # Only include if has storage path
            if updated_media.get("storagePath"):
                uploaded_media.append({
                    "type": updated_media.get("type"),
                    "storagePath": updated_media.get("storagePath"),
                    "url": updated_media.get("url", ""),
                    "md5": updated_media.get("md5", "")
                })

    # Build Firestore document
    doc = {
        "id": post_id,
        "source": "facebook",
        "sourceId": post.get("id", ""),
        "type": post.get("type", "status"),
        "content": post.get("text", ""),
        "publishedAt": post.get("publishedAt", ""),
        "importedAt": datetime.now().isoformat(),
        "media": uploaded_media,
        "stats": post.get("stats", {})
    }

    if dry_run:
        print(f"    [DRY RUN] Would create doc: {post_id}")
        print(f"    [DRY RUN] Media: {len(uploaded_media)} items")
    else:
        try:
            # Use set() for idempotency
            db.collection("fb_posts").document(post_id).set(doc)
            print(f"    [FIRESTORE] Created: {post_id}")

            # Import comments
            import_comments(post_id, post.get("comments", []), db, dry_run)

            progress["importedPosts"].append(post_id)

        except Exception as e:
            print(f"    [ERROR] Firestore write failed: {e}")
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Firebase Importer for ProCaffe FB Content")
    parser.add_argument("--limit", type=int, help="Limit posts to import")
    parser.add_argument("--skip-upload", action="store_true", help="Skip media upload")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--input", type=str, help="Input JSON file (default: data/fb-posts.json)")
    args = parser.parse_args()

    print("=" * 60)
    print("Firebase Importer for ProCaffe FB Content")
    print("=" * 60)

    # Load posts
    input_file = Path(args.input) if args.input else FB_POSTS_FILE
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        print("Run fb-scrape-content.py first to generate this file.")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    posts = data.get("posts", [])
    print(f"\nLoaded {len(posts)} posts from {input_file}")

    if args.limit:
        posts = posts[:args.limit]
        print(f"Limited to {len(posts)} posts")

    # Initialize Firebase
    if not args.dry_run:
        initialize_firebase()
        db = firestore.client()
    else:
        db = None

    # Load progress
    progress = load_progress()

    # Import posts
    success_count = 0
    for i, post in enumerate(posts):
        print(f"\n[{i+1}/{len(posts)}]", end=" ")
        if import_post(post, progress, db, args.skip_upload, args.dry_run):
            success_count += 1

        # Save progress periodically
        if (i + 1) % 10 == 0 and not args.dry_run:
            save_progress(progress)

    # Final save
    if not args.dry_run:
        save_progress(progress)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Posts processed: {len(posts)}")
    print(f"Posts imported: {success_count}")
    print(f"Media uploaded: {len(progress.get('uploadedMedia', []))}")
    print(f"Total in Firestore: {len(progress.get('importedPosts', []))}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made")


if __name__ == "__main__":
    main()
