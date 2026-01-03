#!/usr/bin/env python3
"""
Upload extracted JSON data to Firebase Firestore.

Usage:
  python upload-to-firebase.py --data data/qd999-extracted.json --id forestry --decision-number 999

Prerequisites:
  - Set GOOGLE_APPLICATION_CREDENTIALS env var to service account JSON path
  - Or have Firebase Admin SDK configured
"""

import argparse
import json
import os
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("Error: firebase-admin not installed. Run: pip install firebase-admin")
    exit(1)

def init_firebase():
    """Initialize Firebase Admin SDK."""
    if not firebase_admin._apps:
        # Try environment variable first
        cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            # Try default credentials
            firebase_admin.initialize_app()
    return firestore.client()

def upload_entities(db, collection_name: str, entities: list, batch_size: int = 500):
    """Upload entities to Firestore collection in batches."""
    print(f"  Uploading {len(entities)} documents to {collection_name}...")

    batch = db.batch()
    count = 0

    for entity in entities:
        doc_id = entity.get('id', None)
        if not doc_id:
            print(f"    ⚠ Skipping entity without id: {entity.get('name', 'unknown')}")
            continue

        doc_ref = db.collection(collection_name).document(doc_id)
        batch.set(doc_ref, entity)
        count += 1

        if count % batch_size == 0:
            batch.commit()
            batch = db.batch()
            print(f"    Committed {count} documents...")

    # Commit remaining
    if count % batch_size != 0:
        batch.commit()

    print(f"  ✓ Uploaded {count} documents to {collection_name}")

def upload_document(db, collection_name: str, doc_id: str, data: dict):
    """Upload a single document to Firestore."""
    print(f"  Uploading to {collection_name}/{doc_id}...")
    db.collection(collection_name).document(doc_id).set(data)
    print(f"  ✓ Uploaded {collection_name}/{doc_id}")

def main():
    parser = argparse.ArgumentParser(description='Upload masterplan data to Firebase')
    parser.add_argument('--data', required=True, help='Path to extracted JSON file')
    parser.add_argument('--id', required=True, help='Masterplan ID (e.g., forestry)')
    parser.add_argument('--decision-number', required=True, help='Decision number (e.g., 999)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be uploaded without uploading')

    args = parser.parse_args()

    # Load data
    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: Data file not found: {data_path}")
        return

    with open(data_path) as f:
        data = json.load(f)

    print(f"\nLoaded data from {data_path}")
    print(f"  Entities: {list(data.get('entities', {}).keys())}")
    print(f"  Has overview: {'overview' in data}")
    print(f"  Has aggregates: {'aggregates' in data}")
    print()

    if args.dry_run:
        print("DRY RUN - No data will be uploaded")
        print()

    # Collection names
    mp_id = args.id
    num = args.decision_number

    collections = {
        'overview': f'{mp_id}_overview_{num}',
        'aggregates': f'{mp_id}_aggregates_{num}',
        'search_index': f'{mp_id}_search_index_{num}',
    }

    # Entity collections
    for entity_type in data.get('entities', {}).keys():
        collections[entity_type] = f'{entity_type}_{num}'

    print("Collection mapping:")
    for key, name in collections.items():
        print(f"  {key} -> {name}")
    print()

    if args.dry_run:
        print("Entities to upload:")
        for entity_type, entities in data.get('entities', {}).items():
            print(f"  {entity_type}: {len(entities)} documents")
        return

    # Initialize Firebase
    db = init_firebase()
    print("Firebase initialized")
    print()

    # Upload entities
    for entity_type, entities in data.get('entities', {}).items():
        collection_name = collections[entity_type]
        upload_entities(db, collection_name, entities)

    print()

    # Upload overview
    if 'overview' in data:
        upload_document(db, collections['overview'], 'main', data['overview'])

    # Upload aggregates
    if 'aggregates' in data:
        upload_document(db, collections['aggregates'], 'latest', data['aggregates'])

    print()
    print("Upload complete!")
    print()
    print("Remember to update:")
    print(f"  - src/lib/firebase/constants.ts with collection names")
    print(f"  - Firestore security rules to allow read access")

if __name__ == '__main__':
    main()
