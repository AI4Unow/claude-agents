"""Embedding service using Google Gemini API.

Uses gemini-embedding-001 model for text embeddings.
Integrates with existing GeminiClient for consistent auth/error handling.
"""

import os
import json
import tempfile
from typing import List, Optional

from src.utils.logging import get_logger

logger = get_logger()

# Gemini embedding model
EMBEDDING_MODEL = "gemini-embedding-001"
VECTOR_DIM = 3072  # gemini-embedding-001 outputs 3072 dimensions

_client = None
_available = None  # Cached availability check
_credentials_setup = False


def _setup_gcp_credentials() -> None:
    """Set up GCP credentials from environment JSON."""
    global _credentials_setup
    if _credentials_setup:
        return

    creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if creds_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        # Write JSON to temp file and set env var
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(creds_json)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
            logger.info("embedding_gcp_credentials_setup", path=f.name)

    _credentials_setup = True


def is_available() -> bool:
    """Check if embedding service is available."""
    global _available
    if _available is not None:
        return _available

    try:
        # Test with minimal request
        embedding = get_embedding("test")
        _available = embedding is not None and len(embedding) > 0
    except Exception as e:
        logger.warning("embedding_service_unavailable", error=str(e)[:50])
        _available = False

    return _available


def get_client():
    """Get Google genai client."""
    global _client
    if _client is None:
        from google import genai

        # Prefer API key (simpler), fall back to Vertex AI
        api_key = os.environ.get("GEMINI_API_KEY", "")
        gcp_project = os.environ.get("GCP_PROJECT_ID", "")
        gcp_location = os.environ.get("GCP_LOCATION", "us-central1")

        if api_key:
            _client = genai.Client(api_key=api_key)
            logger.info("embedding_client_init", mode="api_key")
        elif gcp_project:
            # Set up credentials for Vertex AI
            _setup_gcp_credentials()
            _client = genai.Client(
                vertexai=True,
                project=gcp_project,
                location=gcp_location
            )
            logger.info("embedding_client_init", mode="vertexai", project=gcp_project)
        else:
            logger.warning("embedding_no_credentials")
            return None

    return _client


def get_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding using Gemini embedding model.

    Args:
        text: Text to embed

    Returns:
        Embedding vector of 768 dimensions, or None on error
    """
    try:
        from google.genai import types

        client = get_client()
        if not client:
            return None

        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT"
            )
        )

        embedding = response.embeddings[0].values
        logger.debug("embedding_generated", dim=len(embedding))
        return list(embedding)

    except Exception as e:
        logger.error("get_embedding_error", error=str(e)[:100])
        return None


def get_embeddings_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Generate embeddings for multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors (None for any failures)
    """
    try:
        from google.genai import types

        client = get_client()
        if not client:
            return [None] * len(texts)

        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT"
            )
        )

        embeddings = [list(item.values) for item in response.embeddings]
        logger.debug("batch_embeddings_generated", count=len(embeddings))
        return embeddings

    except Exception as e:
        logger.error("get_embeddings_batch_error", error=str(e)[:100])
        return [None] * len(texts)


def get_query_embedding(text: str) -> Optional[List[float]]:
    """Generate embedding for a search query.

    Uses RETRIEVAL_QUERY task type for better search performance.

    Args:
        text: Query text to embed

    Returns:
        Embedding vector of 768 dimensions, or None on error
    """
    try:
        from google.genai import types

        client = get_client()
        if not client:
            return None

        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY"
            )
        )

        embedding = response.embeddings[0].values
        return list(embedding)

    except Exception as e:
        logger.error("get_query_embedding_error", error=str(e)[:100])
        return None
