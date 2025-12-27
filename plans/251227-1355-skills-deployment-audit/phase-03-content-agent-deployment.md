# Phase 3: Content Agent Deployment

## Context
- [Plan Overview](./plan.md)
- Agent code exists: `src/agents/content_generator.py`

## Overview

Deploy ContentAgent as Modal function for content generation tasks.

## Requirements

1. Create Modal function `content_agent()` in main.py
2. Create `skills/content/info.md` skill file
3. Expose via Telegram bot commands

## Implementation

### 1. Add Modal Function to main.py

```python
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=120,
)
async def content_agent(task: Dict):
    """Content Agent - Content generation and transformation."""
    from src.agents.content_generator import process_content_task
    return await process_content_task(task)
```

### 2. Integrate with Telegram Commands

Update `handle_command()` in main.py:

```python
async def handle_command(command: str, user: dict) -> str:
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/translate":
        task = {"payload": {"action": "translate", "text": args, "target": "en"}}
        result = await content_agent.remote.aio(task)
        return result.get("message", "Translation complete")
    elif cmd == "/summarize":
        task = {"payload": {"action": "summarize", "text": args}}
        result = await content_agent.remote.aio(task)
        return result.get("message", "Summary complete")
    # ... existing commands
```

### 3. Create Skill File

Create `skills/content/info.md`:

```markdown
# Content Agent

## Instructions
You are a content generation agent. Write, translate, and transform text.

## Tools Available
- Write content on any topic
- Translate between languages
- Summarize long text
- Rewrite/improve text
- Draft professional emails

## Commands
- /translate <text> - Translate to English
- /summarize <text> - Summarize text
```

## Todo
- [ ] Add content_agent() function to main.py
- [ ] Update handle_command() with content commands
- [ ] Create skills/content/info.md
- [ ] Deploy and test

## Success Criteria

1. `content_agent` appears in Modal app functions
2. /translate and /summarize commands work in Telegram
3. Can generate content on demand
