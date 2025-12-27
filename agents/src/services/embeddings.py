"""Embedding service using Zhipu AI (Z.AI) SDK.

Note: Requires embedding model access in the Z.AI API tier.
If embedding models are not available, this service gracefully degrades.
"""
import os
from typing import List, Optional
import structlog

logger = structlog.get_logger()

# Zhipu AI embedding model
EMBEDDING_MODEL = "embedding-2"
VECTOR_DIM = 1024  # embedding-2 outputs 1024 dimensions

_client = None
_available = None  # Cached availability check


def is_available() -> bool:
    """Check if embedding service is available."""
    global _available
    if _available is not None:
        return _available

    try:
        # Test with minimal request
        embedding = get_embedding("test")
        _available = len(embedding) > 0
    except Exception as e:
        logger.warning("embedding_service_unavailable", error=str(e))
        _available = False

    return _available


def get_client():
    """Get Zhipu AI client."""
    global _client
    if _client is None:
        from zhipuai import ZhipuAI
        api_key = os.environ.get("ZAI_API_KEY", "")
        _client = ZhipuAI(api_key=api_key)
    return _client


def get_embedding(text: str) -> List[float]:
    """Generate embedding using Zhipu AI embedding-2 model.

    Args:
        text: Text to embed (max 512 tokens)

    Returns:
        Embedding vector of 1024 dimensions

    Raises:
        Exception: If embedding model is not available
    """
    client = get_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    client = get_client()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]
