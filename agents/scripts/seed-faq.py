#!/usr/bin/env python3
"""Seed initial FAQ entries for AI4U.now Bot.

Run: modal run agents/scripts/seed-faq.py
"""

import modal

# Build image with src directory
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("firebase-admin", "qdrant-client", "structlog", "google-genai")
    .env({"PYTHONPATH": "/root"})
    .add_local_dir("src", remote_path="/root/src")
)

app = modal.App("faq-seeder")

# Secrets needed
secrets = [
    modal.Secret.from_name("firebase-credentials"),
    modal.Secret.from_name("gcp-credentials"),
    modal.Secret.from_name("qdrant-credentials"),
]


FAQ_ENTRIES = [
    # === Identity (5 entries) ===
    {
        "id": "identity-who-are-you",
        "patterns": ["who are you", "what are you", "introduce yourself", "who is this"],
        "answer": "I'm AI4U.now Bot, a unified AI assistant created by the AI4U.now team. I provide access to multiple AI models (Gemini, Claude, GPT) through a single Telegram interface with 50+ specialized skills.",
        "category": "identity",
    },
    {
        "id": "identity-who-made-you",
        "patterns": ["who made you", "who created you", "who built you", "who is your creator"],
        "answer": "I was created by the AI4U.now team. I'm a unified AI assistant that provides access to multiple AI models through Telegram.",
        "category": "identity",
    },
    {
        "id": "identity-what-models",
        "patterns": ["what models do you use", "what ai models", "which llm", "what language model"],
        "answer": "I use multiple AI models: Gemini (Flash/Pro), Claude (Opus/Sonnet), and GPT series. The best model is automatically selected based on your task.",
        "category": "identity",
    },
    {
        "id": "identity-are-you-claude",
        "patterns": ["are you claude", "are you chatgpt", "are you gpt", "are you gemini"],
        "answer": "I'm AI4U.now Bot, not a single AI model. I'm a unified assistant that uses multiple models (Gemini, Claude, GPT) depending on the task. Think of me as a smart router to the best AI for your needs.",
        "category": "identity",
    },
    {
        "id": "identity-name",
        "patterns": ["what is your name", "your name", "tell me your name"],
        "answer": "My name is AI4U.now Bot. I'm your unified AI assistant!",
        "category": "identity",
    },

    # === Capabilities (5 entries) ===
    {
        "id": "capabilities-what-can-you-do",
        "patterns": ["what can you do", "what are your capabilities", "how can you help", "what do you do"],
        "answer": "I can help with:\n• Research & fact-checking\n• Code & development\n• Design & image generation\n• Document processing (PDF, Word, Excel)\n• Media (video download, image enhance)\n• Automation tasks\n\nUse /skills to browse all 50+ capabilities!",
        "category": "capabilities",
    },
    {
        "id": "capabilities-skills-count",
        "patterns": ["how many skills", "list skills", "show skills", "available skills"],
        "answer": "I have 50+ specialized skills! Use /skills to browse them by category:\n• Research & Analysis\n• Development\n• Design & Media\n• Documents\n• Automation",
        "category": "capabilities",
    },
    {
        "id": "capabilities-web-search",
        "patterns": ["can you search the web", "do you have internet", "can you google", "search online"],
        "answer": "Yes! I can search the web for current information. Just ask me about any topic and I'll find the latest info. I can also read websites if you share a URL.",
        "category": "capabilities",
    },
    {
        "id": "capabilities-images",
        "patterns": ["can you generate images", "create image", "make a picture", "draw"],
        "answer": "Yes! I can generate images using AI. Just describe what you want, like 'generate an image of a sunset over mountains'. Use /skill canvas-design for advanced design work.",
        "category": "capabilities",
    },
    {
        "id": "capabilities-documents",
        "patterns": ["can you read pdf", "process documents", "word documents", "excel files"],
        "answer": "Yes! I can process:\n• PDF files (read, fill forms)\n• Word documents (read, edit)\n• Excel spreadsheets (read, analyze)\n• PowerPoint presentations\n\nJust send me the file!",
        "category": "capabilities",
    },

    # === Commands (6 entries) ===
    {
        "id": "commands-help",
        "patterns": ["how to use", "how does this work", "getting started", "tutorial"],
        "answer": "Getting started is easy!\n\n1. Just send a message to chat\n2. Use /skills to browse capabilities\n3. Use /skill <name> <task> to run specific skills\n\nType /help for all commands!",
        "category": "commands",
    },
    {
        "id": "commands-translate",
        "patterns": ["how to translate", "translation command", "translate text"],
        "answer": "To translate text:\n/translate <your text>\n\nExample: /translate Bonjour le monde\n\nI'll translate it to English!",
        "category": "commands",
    },
    {
        "id": "commands-summarize",
        "patterns": ["how to summarize", "summarize command", "shorten text"],
        "answer": "To summarize text:\n/summarize <your text or URL>\n\nI'll create a concise summary for you!",
        "category": "commands",
    },
    {
        "id": "commands-skill",
        "patterns": ["how to use skill", "run a skill", "execute skill"],
        "answer": "To use a specific skill:\n/skill <name> <your task>\n\nExample: /skill gemini-deep-research quantum computing\n\nUse /skills to see all available skills!",
        "category": "commands",
    },
    {
        "id": "commands-mode",
        "patterns": ["what is mode", "change mode", "auto mode", "routed mode"],
        "answer": "Modes control how I respond:\n• simple - Direct answer (fastest)\n• routed - Auto-select best skill\n• auto - Smart routing based on complexity\n\nChange with: /mode <mode>",
        "category": "commands",
    },
    {
        "id": "commands-clear",
        "patterns": ["clear history", "reset conversation", "start over", "new conversation"],
        "answer": "To clear conversation history:\n/clear\n\nThis resets our chat context. Your settings and tier remain unchanged.",
        "category": "commands",
    },

    # === Troubleshooting (4 entries) ===
    {
        "id": "troubleshoot-slow",
        "patterns": ["why so slow", "taking too long", "response time", "speed"],
        "answer": "Response times depend on:\n• Task complexity (simple: 2-5s, complex: 10-30s)\n• Model used (Gemini is fastest)\n• Current load\n\nTry /mode simple for faster responses!",
        "category": "troubleshooting",
    },
    {
        "id": "troubleshoot-error",
        "patterns": ["got an error", "something went wrong", "not working", "broken"],
        "answer": "Sorry about that! Try:\n1. /clear to reset context\n2. Rephrase your request\n3. Try /mode simple\n\nIf issues persist, the admin will be notified automatically.",
        "category": "troubleshooting",
    },
    {
        "id": "troubleshoot-rate-limit",
        "patterns": ["rate limit", "too many requests", "limit reached", "slow down"],
        "answer": "You may have hit the rate limit. Limits by tier:\n• Guest: 5/min\n• User: 20/min\n• Developer: 50/min\n\nWait a moment and try again!",
        "category": "troubleshooting",
    },
    {
        "id": "troubleshoot-tier",
        "patterns": ["how to upgrade tier", "get more access", "premium", "subscription"],
        "answer": "Tier upgrades are managed by the admin. Current tiers:\n• Guest: Basic chat\n• User: All skills\n• Developer: Debug access\n\nContact the AI4U.now team for upgrades!",
        "category": "troubleshooting",
    },
]


@app.function(image=image, secrets=secrets, timeout=300)
async def seed_faq_entries():
    """Seed all FAQ entries to Firebase and Qdrant using batch embedding."""
    import sys
    sys.path.insert(0, "/root")

    from src.services.firebase import create_faq_entry, FAQEntry
    from src.services.qdrant import upsert_faq_embedding, get_client, FAQ_COLLECTION, VECTOR_DIM
    from src.services.embeddings import get_embeddings_batch
    import structlog

    logger = structlog.get_logger()
    logger.info("seed_faq_start", count=len(FAQ_ENTRIES))

    # Recreate Qdrant collection with correct dimensions
    client = get_client()
    if client:
        from qdrant_client.http import models
        try:
            # Delete old collection if exists
            client.delete_collection(FAQ_COLLECTION)
            logger.info("faq_collection_deleted")
        except Exception:
            pass

        # Create new collection with correct dimensions
        client.create_collection(
            collection_name=FAQ_COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_DIM,
                distance=models.Distance.COSINE
            )
        )
        logger.info("faq_collection_created", dim=VECTOR_DIM)

    # Batch embed all answers in ONE API call (avoids rate limits)
    answers = [data["answer"] for data in FAQ_ENTRIES]
    logger.info("generating_batch_embeddings", count=len(answers))
    embeddings = get_embeddings_batch(answers)
    logger.info("batch_embeddings_complete", success=sum(1 for e in embeddings if e))

    created = 0
    failed = 0

    for i, data in enumerate(FAQ_ENTRIES):
        try:
            embedding = embeddings[i] if i < len(embeddings) else None

            entry = FAQEntry(
                id=data["id"],
                patterns=data["patterns"],
                answer=data["answer"],
                category=data["category"],
                enabled=True,
                embedding=embedding,
            )

            # Create in Firebase
            success = await create_faq_entry(entry)

            if success:
                # Sync to Qdrant
                if embedding:
                    await upsert_faq_embedding(data["id"], embedding, data["answer"])
                created += 1
                logger.info("faq_created", id=data["id"])
            else:
                failed += 1
                logger.warning("faq_create_failed", id=data["id"])

        except Exception as e:
            failed += 1
            logger.error("faq_seed_error", id=data["id"], error=str(e)[:100])

    logger.info("seed_faq_complete", created=created, failed=failed)
    return {"created": created, "failed": failed, "total": len(FAQ_ENTRIES)}


@app.local_entrypoint()
def main():
    """Run the seeder."""
    result = seed_faq_entries.remote()
    print(f"\nFAQ Seeding Complete!")
    print(f"Created: {result['created']}")
    print(f"Failed: {result['failed']}")
    print(f"Total: {result['total']}")
