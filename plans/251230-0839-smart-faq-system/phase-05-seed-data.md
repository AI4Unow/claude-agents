# Phase 5: Seed Data

## Context
- Parent: [plan.md](./plan.md)
- Depends on: [Phase 1](./phase-01-faq-core.md), [Phase 4](./phase-04-admin-commands.md)

## Overview
- **Date:** 2025-12-30
- **Description:** Seed initial FAQ entries for identity, capabilities, commands
- **Priority:** P2
- **Implementation Status:** pending
- **Review Status:** pending

## Key Insights
- Identity FAQs most critical (fix Claude leak)
- Keep answers concise for Telegram
- Generate embeddings for all entries

## Requirements
1. ~20 initial FAQ entries
2. Cover: identity, capabilities, commands, troubleshooting
3. All entries with embeddings

## Initial FAQ Entries

### Identity (5 entries)
```json
[
  {
    "id": "identity-who-are-you",
    "patterns": ["who are you", "what are you", "introduce yourself", "who is this"],
    "answer": "I'm AI4U.now Bot, a unified AI assistant created by the AI4U.now team. I provide access to multiple AI models (Gemini, Claude, GPT) through a single Telegram interface with 50+ specialized skills.",
    "category": "identity"
  },
  {
    "id": "identity-who-made-you",
    "patterns": ["who made you", "who created you", "who built you", "who is your creator"],
    "answer": "I was created by the AI4U.now team. I'm a unified AI assistant that provides access to multiple AI models through Telegram.",
    "category": "identity"
  },
  {
    "id": "identity-what-models",
    "patterns": ["what models do you use", "what ai models", "which llm", "what language model"],
    "answer": "I use multiple AI models: Gemini (2.5/3.0), Claude (Opus/Sonnet), and GPT-5 series. The best model is automatically selected based on your task.",
    "category": "identity"
  },
  {
    "id": "identity-are-you-claude",
    "patterns": ["are you claude", "are you chatgpt", "are you gpt"],
    "answer": "I'm AI4U.now Bot, not a single AI model. I'm a unified assistant that uses multiple models (Gemini, Claude, GPT) depending on the task. Think of me as a smart router to the best AI for your needs.",
    "category": "identity"
  },
  {
    "id": "identity-name",
    "patterns": ["what is your name", "your name", "tell me your name"],
    "answer": "My name is AI4U.now Bot. I'm your unified AI assistant!",
    "category": "identity"
  }
]
```

### Capabilities (5 entries)
```json
[
  {
    "id": "capabilities-what-can-you-do",
    "patterns": ["what can you do", "what are your capabilities", "how can you help", "what do you do"],
    "answer": "I can help with:\n• Research & fact-checking\n• Code & development\n• Design & image generation\n• Document processing (PDF, Word, Excel)\n• Media (video download, image enhance)\n• Automation tasks\n\nUse /skills to browse all 50+ capabilities!",
    "category": "capabilities"
  },
  {
    "id": "capabilities-skills-count",
    "patterns": ["how many skills", "list skills", "show skills", "available skills"],
    "answer": "I have 50+ specialized skills! Use /skills to browse them by category:\n• Research & Analysis\n• Development\n• Design & Media\n• Documents\n• Automation",
    "category": "capabilities"
  },
  {
    "id": "capabilities-web-search",
    "patterns": ["can you search the web", "do you have internet", "can you google", "search online"],
    "answer": "Yes! I can search the web for current information. Just ask me about any topic and I'll find the latest info. I can also read websites if you share a URL.",
    "category": "capabilities"
  },
  {
    "id": "capabilities-images",
    "patterns": ["can you generate images", "create image", "make a picture", "draw"],
    "answer": "Yes! I can generate images using AI. Just describe what you want, like 'generate an image of a sunset over mountains'. Use /skill canvas-design for advanced design work.",
    "category": "capabilities"
  },
  {
    "id": "capabilities-documents",
    "patterns": ["can you read pdf", "process documents", "word documents", "excel files"],
    "answer": "Yes! I can process:\n• PDF files (read, fill forms)\n• Word documents (read, edit)\n• Excel spreadsheets (read, analyze)\n• PowerPoint presentations\n\nJust send me the file!",
    "category": "capabilities"
  }
]
```

### Commands (6 entries)
```json
[
  {
    "id": "commands-help",
    "patterns": ["how to use", "how does this work", "getting started", "tutorial"],
    "answer": "Getting started is easy!\n\n1. Just send a message to chat\n2. Use /skills to browse capabilities\n3. Use /skill <name> <task> to run specific skills\n\nType /help for all commands!",
    "category": "commands"
  },
  {
    "id": "commands-translate",
    "patterns": ["how to translate", "translation command", "translate text"],
    "answer": "To translate text:\n/translate <your text>\n\nExample: /translate Bonjour le monde\n\nI'll translate it to English!",
    "category": "commands"
  },
  {
    "id": "commands-summarize",
    "patterns": ["how to summarize", "summarize command", "shorten text"],
    "answer": "To summarize text:\n/summarize <your text or URL>\n\nI'll create a concise summary for you!",
    "category": "commands"
  },
  {
    "id": "commands-skill",
    "patterns": ["how to use skill", "run a skill", "execute skill"],
    "answer": "To use a specific skill:\n/skill <name> <your task>\n\nExample: /skill gemini-deep-research quantum computing\n\nUse /skills to see all available skills!",
    "category": "commands"
  },
  {
    "id": "commands-mode",
    "patterns": ["what is mode", "change mode", "auto mode", "routed mode"],
    "answer": "Modes control how I respond:\n• simple - Direct answer (fastest)\n• routed - Auto-select best skill\n• auto - Smart routing based on complexity\n\nChange with: /mode <mode>",
    "category": "commands"
  },
  {
    "id": "commands-clear",
    "patterns": ["clear history", "reset conversation", "start over", "new conversation"],
    "answer": "To clear conversation history:\n/clear\n\nThis resets our chat context. Your settings and tier remain unchanged.",
    "category": "commands"
  }
]
```

### Troubleshooting (4 entries)
```json
[
  {
    "id": "troubleshoot-slow",
    "patterns": ["why so slow", "taking too long", "response time", "speed"],
    "answer": "Response times depend on:\n• Task complexity (simple: 2-5s, complex: 10-30s)\n• Model used (Gemini is fastest)\n• Current load\n\nTry /mode simple for faster responses!",
    "category": "troubleshooting"
  },
  {
    "id": "troubleshoot-error",
    "patterns": ["got an error", "something went wrong", "not working", "broken"],
    "answer": "Sorry about that! Try:\n1. /clear to reset context\n2. Rephrase your request\n3. Try /mode simple\n\nIf issues persist, the admin will be notified automatically.",
    "category": "troubleshooting"
  },
  {
    "id": "troubleshoot-rate-limit",
    "patterns": ["rate limit", "too many requests", "limit reached", "slow down"],
    "answer": "You may have hit the rate limit. Limits by tier:\n• Guest: 5/min\n• User: 20/min\n• Developer: 50/min\n\nWait a moment and try again!",
    "category": "troubleshooting"
  },
  {
    "id": "troubleshoot-tier",
    "patterns": ["how to upgrade tier", "get more access", "premium", "subscription"],
    "answer": "Tier upgrades are managed by the admin. Current tiers:\n• Guest: Basic chat\n• User: All skills\n• Developer: Debug access\n\nContact the AI4U.now team for upgrades!",
    "category": "troubleshooting"
  }
]
```

## Implementation

### Seed Script (main.py or separate script)
```python
async def seed_faq_entries():
    """Seed initial FAQ entries."""
    from src.services.firebase import create_faq_entry, FAQEntry
    from src.services.qdrant import get_embedding

    entries = [
        # Identity
        FAQEntry(id="identity-who-are-you", patterns=["who are you", "what are you", "introduce yourself"], ...),
        # ... all entries from above
    ]

    for entry in entries:
        # Generate embedding
        entry.embedding = await get_embedding(entry.answer)
        await create_faq_entry(entry)
        print(f"Seeded: {entry.id}")

    print(f"Seeded {len(entries)} FAQ entries")
```

## Todo List
- [ ] Create seed script with all entries
- [ ] Generate embeddings for each entry
- [ ] Run seed script on Modal
- [ ] Verify entries in Firebase console
- [ ] Test FAQ responses in Telegram

## Success Criteria
- All 20 entries created in Firebase
- All embeddings synced to Qdrant
- "who are you" returns branded answer
- Identity questions never leak Claude

## Risk Assessment
- **Duplicate entries:** Use upsert pattern
- **Embedding failures:** Retry logic

## Security Considerations
- Seed script should be run once
- Consider idempotent upsert

## Next Steps
- Deploy and test full FAQ flow
- Monitor FAQ hit rate
- Add more entries based on usage
