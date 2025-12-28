#!/usr/bin/env python3
"""
Knowledge Base Query CLI for ProCaffe Second Brain.

Semantic search and RAG-powered Q&A using Pinecone + Gemini.

Usage:
    python3 kb-query.py "Máy espresso có bảo hành không?"
    python3 kb-query.py "Gợi ý video về latte art" --namespace facebook
    python3 kb-query.py --interactive

Requirements:
    - PINECONE_API_KEY in config.py or env var
    - GEMINI_API_KEY in env var
"""

import argparse
import json
import os
import sys
from typing import Optional

import google.generativeai as genai
from pinecone import Pinecone

from config import DATA_DIR

# Pinecone Configuration
PINECONE_INDEX_NAME = "procaffe-kb"

# Default namespaces to search
DEFAULT_NAMESPACES = ["facebook", "products", "faqs"]

# Global instances
_pinecone_index = None


def get_pinecone_api_key() -> str:
    """Get Pinecone API key from env or config."""
    api_key = os.environ.get("PINECONE_API_KEY")
    if api_key:
        return api_key
    try:
        from config import PINECONE_API_KEY
        return PINECONE_API_KEY
    except ImportError:
        pass
    print("ERROR: PINECONE_API_KEY not found")
    sys.exit(1)


def initialize_pinecone():
    """Initialize Pinecone client and index."""
    global _pinecone_index
    if _pinecone_index is not None:
        return _pinecone_index

    api_key = get_pinecone_api_key()
    pc = Pinecone(api_key=api_key)
    _pinecone_index = pc.Index(PINECONE_INDEX_NAME)
    return _pinecone_index


def initialize_gemini():
    """Initialize Gemini for embeddings and generation."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found")
        sys.exit(1)
    genai.configure(api_key=api_key)


def embed_query(text: str) -> list[float]:
    """Generate query embedding using Gemini."""
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_query"  # Query-optimized embedding
    )
    return result["embedding"]


def semantic_search(
    query: str,
    namespaces: list[str] = None,
    top_k: int = 5,
    min_score: float = 0.5
) -> list[dict]:
    """Search Pinecone for relevant context."""
    index = initialize_pinecone()
    namespaces = namespaces or DEFAULT_NAMESPACES

    # Generate query embedding
    query_embedding = embed_query(query)

    # Search across namespaces
    all_results = []
    for ns in namespaces:
        try:
            response = index.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=ns,
                include_metadata=True
            )
            for match in response.get("matches", []):
                match["namespace"] = ns
                all_results.append(match)
        except Exception as e:
            print(f"  [WARN] Error searching {ns}: {e}")

    # Sort by score and filter
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    filtered = [r for r in all_results if r.get("score", 0) >= min_score]

    return filtered[:top_k]


def format_search_results(results: list[dict]) -> str:
    """Format search results for display."""
    if not results:
        return "No relevant results found."

    output = []
    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        ns = r.get("namespace", "unknown")
        meta = r.get("metadata", {})
        preview = meta.get("text_preview", "")[:100]
        engagement = meta.get("engagement", 0)
        source = meta.get("source", ns)

        output.append(f"{i}. [{source}] Score: {score:.3f}")
        output.append(f"   Preview: {preview}...")
        output.append(f"   Engagement: {engagement}")
        output.append("")

    return "\n".join(output)


def rag_answer(
    question: str,
    namespaces: list[str] = None,
    context_limit: int = 5,
    verbose: bool = False
) -> str:
    """Generate answer using RAG (Retrieval-Augmented Generation)."""
    # 1. Retrieve context from Pinecone
    results = semantic_search(question, namespaces, top_k=context_limit)

    if not results:
        return "Xin lỗi, tôi không tìm thấy thông tin liên quan trong hệ thống."

    if verbose:
        print("\n--- Retrieved Context ---")
        print(format_search_results(results))
        print("--- End Context ---\n")

    # 2. Build context string
    context_parts = []
    for r in results:
        meta = r.get("metadata", {})
        preview = meta.get("text_preview", "")
        source = meta.get("source", "unknown")
        if preview:
            context_parts.append(f"[{source}]: {preview}")

    context = "\n".join(context_parts)

    # 3. Generate with Gemini
    model = genai.GenerativeModel("gemini-3-flash-preview")
    prompt = f"""Bạn là trợ lý AI của ProCaffe - công ty cung cấp máy pha cà phê chuyên nghiệp cho khách sạn, nhà hàng, quán cafe tại Việt Nam.

Trả lời câu hỏi dựa trên context bên dưới. Nếu context không đủ thông tin, hãy nói rằng bạn không có đủ thông tin nhưng vẫn cố gắng hỗ trợ.

Context:
{context}

Câu hỏi: {question}

Hướng dẫn:
- Trả lời ngắn gọn, chuyên nghiệp
- Sử dụng tiếng Việt
- Nếu là câu hỏi về sản phẩm, đề cập đến liên hệ Procaffe để biết thêm chi tiết
- Nếu context chứa video/content liên quan, có thể đề cập

Trả lời:"""

    response = model.generate_content(prompt)
    return response.text


def interactive_mode():
    """Run interactive Q&A session."""
    print("\n" + "="*60)
    print("ProCaffe Knowledge Base - Interactive Mode")
    print("="*60)
    print("Type your questions in Vietnamese or English.")
    print("Commands: /quit, /search <query>, /stats")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("❓ You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["/quit", "/exit", "/q"]:
            print("Goodbye!")
            break

        if user_input.startswith("/search "):
            query = user_input[8:]
            results = semantic_search(query)
            print("\n" + format_search_results(results))
            continue

        if user_input == "/stats":
            index = initialize_pinecone()
            stats = index.describe_index_stats()
            print(f"\nIndex Stats: {json.dumps(stats.to_dict(), indent=2)}\n")
            continue

        # RAG answer
        print("\n🤖 ProCaffe: ", end="")
        answer = rag_answer(user_input, verbose=False)
        print(answer)
        print()


def main():
    parser = argparse.ArgumentParser(description="ProCaffe KB Query CLI")
    parser.add_argument("query", nargs="?", help="Question to ask")
    parser.add_argument("--namespace", "-n", action="append",
                        help="Namespace(s) to search (can repeat)")
    parser.add_argument("--search-only", "-s", action="store_true",
                        help="Only show search results, no RAG")
    parser.add_argument("--top-k", "-k", type=int, default=5,
                        help="Number of results to retrieve")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show retrieved context")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactive mode")
    args = parser.parse_args()

    # Initialize
    initialize_gemini()
    initialize_pinecone()

    # Interactive mode
    if args.interactive or not args.query:
        interactive_mode()
        return

    # Single query mode
    namespaces = args.namespace or DEFAULT_NAMESPACES
    print(f"\n🔍 Query: {args.query}")
    print(f"📁 Namespaces: {namespaces}\n")

    if args.search_only:
        results = semantic_search(args.query, namespaces, args.top_k)
        print(format_search_results(results))
    else:
        answer = rag_answer(args.query, namespaces, args.top_k, args.verbose)
        print(f"🤖 Answer:\n{answer}")


if __name__ == "__main__":
    main()
