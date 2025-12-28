#!/usr/bin/env python3
"""
Firebase Admin CLI for ProCaffe.

Access Firestore and Storage using service account credentials.

Usage:
    python3 firebase-admin.py firestore list-collections
    python3 firebase-admin.py firestore get users/user123
    python3 firebase-admin.py storage list
    python3 firebase-admin.py storage upload local.png images/remote.png
"""

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

from config import (
    FIREBASE_SERVICE_ACCOUNT,
    FIREBASE_PROJECT_ID,
    FIREBASE_STORAGE_BUCKET,
)

# Global app instance
_app = None


def initialize_firebase():
    """Initialize Firebase Admin SDK with service account."""
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


# ============== FIRESTORE COMMANDS ==============

def fs_list_collections(args):
    """List all top-level collections."""
    initialize_firebase()
    db = firestore.client()

    collections = db.collections()
    count = 0
    for col in collections:
        print(col.id)
        count += 1

    print(f"\n--- {count} collections ---")


def fs_get(args):
    """Get document by path."""
    initialize_firebase()
    db = firestore.client()

    doc_ref = db.document(args.path)
    doc = doc_ref.get()

    if not doc.exists:
        print(f"Document not found: {args.path}")
        sys.exit(1)

    data = doc.to_dict()
    if args.json:
        print(json.dumps(data, indent=2, default=str, ensure_ascii=False))
    else:
        print(f"ID: {doc.id}")
        print(f"Path: {args.path}")
        print("Data:")
        for k, v in data.items():
            print(f"  {k}: {v}")


def fs_set(args):
    """Set/update document."""
    initialize_firebase()
    db = firestore.client()

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        sys.exit(1)

    if args.dry_run:
        print(f"[DRY RUN] Would set {args.path}:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    doc_ref = db.document(args.path)
    if args.merge:
        doc_ref.set(data, merge=True)
        print(f"Merged: {args.path}")
    else:
        doc_ref.set(data)
        print(f"Set: {args.path}")


def fs_delete(args):
    """Delete document."""
    initialize_firebase()
    db = firestore.client()

    if args.dry_run:
        print(f"[DRY RUN] Would delete: {args.path}")
        return

    doc_ref = db.document(args.path)
    doc_ref.delete()
    print(f"Deleted: {args.path}")


def fs_query(args):
    """Query collection with filters."""
    initialize_firebase()
    db = firestore.client()

    col_ref = db.collection(args.collection)

    # Parse --where filters (format: field==value or field>value)
    if args.where:
        for w in args.where:
            if "==" in w:
                field, value = w.split("==", 1)
                col_ref = col_ref.where(filter=FieldFilter(field.strip(), "==", _parse_value(value.strip())))
            elif ">=" in w:
                field, value = w.split(">=", 1)
                col_ref = col_ref.where(filter=FieldFilter(field.strip(), ">=", _parse_value(value.strip())))
            elif "<=" in w:
                field, value = w.split("<=", 1)
                col_ref = col_ref.where(filter=FieldFilter(field.strip(), "<=", _parse_value(value.strip())))
            elif ">" in w:
                field, value = w.split(">", 1)
                col_ref = col_ref.where(filter=FieldFilter(field.strip(), ">", _parse_value(value.strip())))
            elif "<" in w:
                field, value = w.split("<", 1)
                col_ref = col_ref.where(filter=FieldFilter(field.strip(), "<", _parse_value(value.strip())))

    if args.limit:
        col_ref = col_ref.limit(args.limit)

    docs = col_ref.stream()
    count = 0
    for doc in docs:
        count += 1
        if args.json:
            print(json.dumps({"id": doc.id, **doc.to_dict()}, default=str, ensure_ascii=False))
        else:
            print(f"{doc.id}: {doc.to_dict()}")

    print(f"\n--- {count} documents ---")


def fs_list_docs(args):
    """List documents in a collection."""
    initialize_firebase()
    db = firestore.client()

    col_ref = db.collection(args.collection)
    if args.limit:
        col_ref = col_ref.limit(args.limit)

    docs = col_ref.stream()
    count = 0
    for doc in docs:
        count += 1
        if args.json:
            print(json.dumps({"id": doc.id, **doc.to_dict()}, default=str, ensure_ascii=False))
        else:
            print(f"{doc.id}")

    print(f"\n--- {count} documents ---")


def _parse_value(val):
    """Parse string value to appropriate type."""
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


# ============== STORAGE COMMANDS ==============

def st_list(args):
    """List files in storage bucket."""
    initialize_firebase()
    bucket = storage.bucket()

    prefix = args.prefix if args.prefix else ""
    blobs = bucket.list_blobs(prefix=prefix, max_results=args.limit or 100)

    count = 0
    total_size = 0
    for blob in blobs:
        count += 1
        total_size += blob.size or 0
        if args.json:
            print(json.dumps({
                "name": blob.name,
                "size": blob.size,
                "updated": str(blob.updated) if blob.updated else None,
                "content_type": blob.content_type,
            }))
        else:
            size_str = _format_size(blob.size or 0)
            print(f"{blob.name} ({size_str})")

    print(f"\n--- {count} files, {_format_size(total_size)} total ---")


def st_upload(args):
    """Upload file to storage."""
    initialize_firebase()
    bucket = storage.bucket()

    local_path = Path(args.local)
    if not local_path.exists():
        print(f"Local file not found: {args.local}")
        sys.exit(1)

    if args.dry_run:
        print(f"[DRY RUN] Would upload: {args.local} -> {args.remote}")
        return

    blob = bucket.blob(args.remote)
    blob.upload_from_filename(str(local_path))
    print(f"Uploaded: {args.local} -> {args.remote}")


def st_download(args):
    """Download file from storage."""
    initialize_firebase()
    bucket = storage.bucket()

    local_path = Path(args.local)

    if args.dry_run:
        print(f"[DRY RUN] Would download: {args.remote} -> {args.local}")
        return

    blob = bucket.blob(args.remote)
    if not blob.exists():
        print(f"Remote file not found: {args.remote}")
        sys.exit(1)

    local_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(local_path))
    print(f"Downloaded: {args.remote} -> {args.local}")


def st_delete(args):
    """Delete file from storage."""
    initialize_firebase()
    bucket = storage.bucket()

    if args.dry_run:
        print(f"[DRY RUN] Would delete: {args.remote}")
        return

    blob = bucket.blob(args.remote)
    if not blob.exists():
        print(f"File not found: {args.remote}")
        sys.exit(1)

    blob.delete()
    print(f"Deleted: {args.remote}")


def st_url(args):
    """Get signed URL for file."""
    initialize_firebase()
    bucket = storage.bucket()

    blob = bucket.blob(args.remote)
    if not blob.exists():
        print(f"File not found: {args.remote}")
        sys.exit(1)

    url = blob.generate_signed_url(
        expiration=timedelta(seconds=args.expires),
        method="GET"
    )
    print(url)


def _format_size(size_bytes):
    """Format bytes to human readable."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# ============== CLI SETUP ==============

def main():
    parser = argparse.ArgumentParser(
        description="Firebase Admin CLI for ProCaffe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Firestore
  python3 firebase-admin.py fs list-collections
  python3 firebase-admin.py fs get users/abc123
  python3 firebase-admin.py fs set users/abc123 '{"name":"Test"}'
  python3 firebase-admin.py fs query users --where "active==true" --limit 10

  # Storage
  python3 firebase-admin.py st list
  python3 firebase-admin.py st upload ./logo.png images/logo.png
  python3 firebase-admin.py st download images/logo.png ./logo.png
  python3 firebase-admin.py st url images/logo.png --expires 3600
"""
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ===== FIRESTORE =====
    fs_parser = subparsers.add_parser("firestore", aliases=["fs"], help="Firestore commands")
    fs_sub = fs_parser.add_subparsers(dest="action", required=True)

    # fs list-collections
    fs_list_col = fs_sub.add_parser("list-collections", aliases=["lc"], help="List collections")
    fs_list_col.set_defaults(func=fs_list_collections)

    # fs list <collection>
    fs_list = fs_sub.add_parser("list", aliases=["ls"], help="List documents in collection")
    fs_list.add_argument("collection", help="Collection path")
    fs_list.add_argument("--limit", type=int, help="Max documents")
    fs_list.add_argument("--json", action="store_true", help="JSON output")
    fs_list.set_defaults(func=fs_list_docs)

    # fs get <path>
    fs_get_p = fs_sub.add_parser("get", help="Get document")
    fs_get_p.add_argument("path", help="Document path (e.g., users/abc123)")
    fs_get_p.add_argument("--json", action="store_true", help="JSON output")
    fs_get_p.set_defaults(func=fs_get)

    # fs set <path> <data>
    fs_set_p = fs_sub.add_parser("set", help="Set document")
    fs_set_p.add_argument("path", help="Document path")
    fs_set_p.add_argument("data", help="JSON data")
    fs_set_p.add_argument("--merge", action="store_true", help="Merge with existing")
    fs_set_p.add_argument("--dry-run", action="store_true", help="Show what would be done")
    fs_set_p.set_defaults(func=fs_set)

    # fs delete <path>
    fs_del_p = fs_sub.add_parser("delete", aliases=["rm"], help="Delete document")
    fs_del_p.add_argument("path", help="Document path")
    fs_del_p.add_argument("--dry-run", action="store_true", help="Show what would be done")
    fs_del_p.set_defaults(func=fs_delete)

    # fs query <collection>
    fs_query_p = fs_sub.add_parser("query", aliases=["q"], help="Query collection")
    fs_query_p.add_argument("collection", help="Collection path")
    fs_query_p.add_argument("--where", "-w", action="append", help="Filter (e.g., status==active)")
    fs_query_p.add_argument("--limit", type=int, help="Max results")
    fs_query_p.add_argument("--json", action="store_true", help="JSON output")
    fs_query_p.set_defaults(func=fs_query)

    # ===== STORAGE =====
    st_parser = subparsers.add_parser("storage", aliases=["st"], help="Storage commands")
    st_sub = st_parser.add_subparsers(dest="action", required=True)

    # st list
    st_list_p = st_sub.add_parser("list", aliases=["ls"], help="List files")
    st_list_p.add_argument("prefix", nargs="?", default="", help="Path prefix")
    st_list_p.add_argument("--limit", type=int, help="Max files")
    st_list_p.add_argument("--json", action="store_true", help="JSON output")
    st_list_p.set_defaults(func=st_list)

    # st upload
    st_upload_p = st_sub.add_parser("upload", aliases=["up"], help="Upload file")
    st_upload_p.add_argument("local", help="Local file path")
    st_upload_p.add_argument("remote", help="Remote path in bucket")
    st_upload_p.add_argument("--dry-run", action="store_true", help="Show what would be done")
    st_upload_p.set_defaults(func=st_upload)

    # st download
    st_download_p = st_sub.add_parser("download", aliases=["dl"], help="Download file")
    st_download_p.add_argument("remote", help="Remote path in bucket")
    st_download_p.add_argument("local", help="Local file path")
    st_download_p.add_argument("--dry-run", action="store_true", help="Show what would be done")
    st_download_p.set_defaults(func=st_download)

    # st delete
    st_delete_p = st_sub.add_parser("delete", aliases=["rm"], help="Delete file")
    st_delete_p.add_argument("remote", help="Remote path in bucket")
    st_delete_p.add_argument("--dry-run", action="store_true", help="Show what would be done")
    st_delete_p.set_defaults(func=st_delete)

    # st url
    st_url_p = st_sub.add_parser("url", help="Get signed URL")
    st_url_p.add_argument("remote", help="Remote path in bucket")
    st_url_p.add_argument("--expires", type=int, default=3600, help="Expiration in seconds (default: 3600)")
    st_url_p.set_defaults(func=st_url)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
