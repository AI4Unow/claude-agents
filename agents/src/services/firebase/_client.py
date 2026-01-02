"""Firebase client initialization and shared utilities.

Thread-safe singleton pattern using lru_cache for Firebase and Storage.
"""
import json
import os
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import storage

from src.utils.logging import get_logger

logger = get_logger()


@lru_cache(maxsize=1)
def _init_firebase_once():
    """Initialize Firebase once (thread-safe via lru_cache).

    Security:
    - Thread-safe singleton pattern using lru_cache
    - Prevents double initialization race condition
    - Fails fast if credentials not configured

    Returns:
        Firestore client instance

    Raises:
        ValueError: If FIREBASE_CREDENTIALS not set
    """
    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not cred_json:
        raise ValueError("FIREBASE_CREDENTIALS not set")

    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("firebase_initialized", project=cred_dict.get("project_id"))
    return db


def get_db():
    """Get Firestore client (singleton).

    Returns:
        Firestore client instance (cached after first call)
    """
    return _init_firebase_once()


@lru_cache(maxsize=1)
def _init_storage_once():
    """Initialize Cloud Storage once (thread-safe)."""
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", "ai4unow.firebasestorage.app")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    logger.info("storage_initialized", bucket=bucket_name)
    return bucket


def get_bucket():
    """Get Storage bucket (singleton).

    Returns:
        Storage bucket instance
    """
    return _init_storage_once()


# Collection name constants
class Collections:
    """Firestore collection names."""
    USERS = "users"
    AGENTS = "agents"
    TASKS = "tasks"
    TOKENS = "tokens"
    LOGS = "logs"
    SKILLS = "skills"
    ENTITIES = "entities"
    DECISIONS = "decisions"
    OBSERVATIONS = "observations"
    TASK_QUEUE = "task_queue"
    REMINDERS = "reminders"
    REPORTS = "reports"
    USER_TIERS = "user_tiers"
    FAQ_ENTRIES = "faq_entries"
    CONTENT_FILES = "content_files"
