#!/usr/bin/env python3
"""
FAQ Import to Firestore for ProCaffe Second Brain.

Imports FAQ entries from CSV to Firestore `faqs` collection.

Usage:
    python3 faq-import-to-firestore.py                  # Import all FAQs
    python3 faq-import-to-firestore.py --dry-run        # Show what would be done
    python3 faq-import-to-firestore.py --limit 10       # Import first 10 only

Requirements:
    - firebase_service_account.json in project root
"""

import argparse
import csv
import hashlib
import sys
from datetime import datetime
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from config import (
    FIREBASE_SERVICE_ACCOUNT,
    FIREBASE_PROJECT_ID,
    PROJECT_DIR,
)

# FAQ CSV file location
FAQ_CSV_FILE = PROJECT_DIR / "data" / "faqs-expanded.csv"

# Global Firebase instance
_firebase_app = None


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


def generate_faq_id(question: str) -> str:
    """Generate deterministic ID from question hash."""
    # Use first 8 chars of MD5 hash for short, unique IDs
    question_hash = hashlib.md5(question.encode('utf-8')).hexdigest()[:8]
    return f"faq_{question_hash}"


def parse_faq_csv(file_path: Path, limit: int = None) -> list[dict]:
    """Parse FAQ CSV file and return list of FAQ entries."""
    faqs = []

    if not file_path.exists():
        print(f"ERROR: FAQ file not found: {file_path}")
        sys.exit(1)

    # Try utf-8-sig first (handles BOM), fallback to utf-8
    encodings = ['utf-8-sig', 'utf-8', 'latin-1']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break

                    question = row.get('question', '').strip()
                    answer = row.get('answer', '').strip()

                    if not question or not answer:
                        continue

                    faqs.append({
                        'question': question,
                        'answer': answer,
                        'category': row.get('category', 'general').strip() or 'general',
                    })
            break  # Success, exit encoding loop
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"ERROR parsing CSV: {e}")
            sys.exit(1)

    return faqs


def import_faqs_to_firestore(db, faqs: list[dict], dry_run: bool = False) -> int:
    """Import FAQ entries to Firestore `faqs` collection."""
    collection_ref = db.collection('faqs')
    imported_count = 0
    skipped_count = 0

    print(f"\n{'='*60}")
    print(f"Importing {len(faqs)} FAQs to Firestore")
    print(f"{'='*60}")

    for i, faq in enumerate(faqs):
        doc_id = generate_faq_id(faq['question'])

        # Check if already exists
        existing_doc = collection_ref.document(doc_id).get()
        if existing_doc.exists:
            print(f"  [{i+1}/{len(faqs)}] SKIP (exists): {doc_id}")
            skipped_count += 1
            continue

        # Prepare document
        doc_data = {
            'id': doc_id,
            'question': faq['question'],
            'answer': faq['answer'],
            'category': faq.get('category', 'general'),
            'source': 'csv',
            'imported_at': datetime.now().isoformat(),
        }

        if dry_run:
            print(f"  [{i+1}/{len(faqs)}] DRY-RUN: {doc_id} - {faq['question'][:40]}...")
            imported_count += 1
            continue

        # Write to Firestore
        try:
            collection_ref.document(doc_id).set(doc_data)
            print(f"  [{i+1}/{len(faqs)}] IMPORTED: {doc_id}")
            imported_count += 1
        except Exception as e:
            print(f"  [{i+1}/{len(faqs)}] ERROR: {e}")

    return imported_count, skipped_count


def main():
    parser = argparse.ArgumentParser(description="Import FAQs to Firestore")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--limit", type=int, help="Limit FAQs to import")
    parser.add_argument("--file", type=str, help="Custom FAQ CSV file path")
    args = parser.parse_args()

    print("="*60)
    print("ProCaffe FAQ Import to Firestore")
    print("="*60)

    # Determine FAQ file
    faq_file = Path(args.file) if args.file else FAQ_CSV_FILE
    print(f"Source: {faq_file}")

    # Parse CSV
    faqs = parse_faq_csv(faq_file, args.limit)
    print(f"Parsed {len(faqs)} FAQ entries")

    if not faqs:
        print("No FAQs found to import")
        return

    # Initialize Firebase
    if not args.dry_run:
        db = initialize_firebase()
    else:
        db = None
        print("[DRY RUN MODE]")

    # Import to Firestore
    if args.dry_run:
        # Simulate import without Firebase
        for i, faq in enumerate(faqs):
            doc_id = generate_faq_id(faq['question'])
            print(f"  [{i+1}/{len(faqs)}] DRY-RUN: {doc_id} - {faq['question'][:40]}...")
        imported_count = len(faqs)
        skipped_count = 0
    else:
        imported_count, skipped_count = import_faqs_to_firestore(db, faqs, args.dry_run)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total FAQs: {len(faqs)}")
    print(f"Imported: {imported_count}")
    print(f"Skipped (existing): {skipped_count}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made")


if __name__ == "__main__":
    main()
