# Phase 6: Data & Content Agents

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 5 - GitHub Agent](./phase-05-github-agent.md)

## Overview

**Priority:** P2 - Feature Agents
**Status:** Pending
**Effort:** 4h

Build Data Agent (scheduled analytics/reporting) and Content Agent (on-demand content generation). Both process tasks from Firebase queue.

## Requirements

### Data Agent
- Generate daily/weekly reports
- Analyze data from various sources
- Create summaries and insights
- Export to various formats

### Content Agent
- Generate written content (emails, articles, summaries)
- Translate text between languages
- Rewrite/improve existing text
- Create structured documents

---

## Part A: Data Agent

### Capabilities

| Capability | Description |
|------------|-------------|
| `daily_summary` | Generate daily activity summary |
| `analyze_data` | Analyze provided data with insights |
| `generate_report` | Create formatted report |
| `export_csv` | Export data as CSV |

### Implementation

#### Add Data Agent to main.py

```python
# Add to main.py

@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("0 8 * * *"),  # Daily at 8 AM
    timeout=300,
    retries=2,  # Retry on failure (context engineering)
)
async def data_agent_scheduled():
    """Data Agent - Daily scheduled reports."""
    from src.agents.data_processor import generate_daily_summary
    await generate_daily_summary()

@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("*/10 * * * *"),  # Every 10 minutes
    timeout=180,  # 3 minute max per batch (execution limit)
    retries=2,
)
async def process_data_queue():
    """Process pending data tasks from queue."""
    from src.services import firebase
    from src.agents.data_processor import process_data_task

    while True:
        task = await firebase.claim_task("data", "data-processor")
        if not task:
            break
        await process_data_task(task)
```

#### Create src/agents/data_processor.py

```python
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
from src.agents.base import BaseAgent
from src.services import firebase, qdrant, embeddings
from src.services.anthropic import get_claude_response

class DataAgent(BaseAgent):
    """Data Agent - Analytics and reporting."""

    def __init__(self):
        super().__init__("data")

    async def process(self, task: Dict) -> Dict:
        """Process a data task from queue."""
        action = task.get("payload", {}).get("action", "")
        user_id = task.get("payload", {}).get("user_id")

        handlers = {
            "daily_summary": self.daily_summary,
            "analyze_data": self.analyze_data,
            "generate_report": self.generate_report,
        }

        handler = handlers.get(action, self.handle_unknown)
        result = await handler(task.get("payload", {}))

        if user_id and result.get("message"):
            await self.notify_user(user_id, result["message"])

        return result

    async def daily_summary(self, payload: Dict) -> Dict:
        """Generate daily activity summary."""
        # Get yesterday's logs
        yesterday = datetime.utcnow() - timedelta(days=1)

        db = firebase.get_db()
        logs = db.collection("logs")\
            .where("timestamp", ">=", yesterday)\
            .order_by("timestamp")\
            .get()

        log_entries = [doc.to_dict() for doc in logs]

        # Get task statistics
        tasks = db.collection("tasks")\
            .where("createdAt", ">=", yesterday)\
            .get()

        task_stats = {
            "total": len(list(tasks)),
            "completed": len([t for t in tasks if t.to_dict().get("status") == "done"]),
            "failed": len([t for t in tasks if t.to_dict().get("status") == "failed"]),
        }

        # Generate summary with Claude
        summary = await get_claude_response(
            user_message=f"""Generate a daily activity summary:

Log entries: {len(log_entries)}
Tasks: {json.dumps(task_stats)}

Provide a brief, actionable summary of agent activity.""",
            system_prompt="You are a data analyst. Be concise and highlight important metrics."
        )

        return {
            "status": "success",
            "summary": summary,
            "stats": task_stats,
            "message": f"📊 Daily Summary ({yesterday.strftime('%Y-%m-%d')}):\n\n{summary}"
        }

    async def analyze_data(self, payload: Dict) -> Dict:
        """Analyze provided data."""
        data = payload.get("data", "")
        question = payload.get("question", "Analyze this data")

        if not data:
            return {"error": "No data provided"}

        analysis = await get_claude_response(
            user_message=f"""Analyze this data and answer the question.

Data:
{data[:5000]}  # Limit data size

Question: {question}""",
            system_prompt="You are a data analyst. Provide clear insights with actionable recommendations."
        )

        return {
            "status": "success",
            "analysis": analysis,
            "message": f"📈 Data Analysis:\n\n{analysis}"
        }

    async def generate_report(self, payload: Dict) -> Dict:
        """Generate a formatted report."""
        topic = payload.get("topic", "")
        data = payload.get("data", {})
        format_type = payload.get("format", "markdown")

        report = await get_claude_response(
            user_message=f"""Generate a {format_type} report about: {topic}

Data: {json.dumps(data)[:3000]}

Create a well-structured report with sections, key findings, and recommendations.""",
            system_prompt="You are a report writer. Create professional, clear reports."
        )

        return {
            "status": "success",
            "report": report,
            "message": f"📄 Report: {topic}\n\n{report[:2000]}..."
        }

    async def handle_unknown(self, payload: Dict) -> Dict:
        return {"error": "Unknown action"}

    async def notify_user(self, user_id: str, message: str):
        """
        Notify user via Telegram using forward_to_user pattern.

        Uses direct forwarding to prevent "telephone game" data loss
        where supervisor paraphrases responses incorrectly.
        """
        # Use inherited forward_to_user from BaseAgent
        await self.forward_to_user(
            user_id=user_id,
            message=message,
            bypass_supervisor=True  # Send directly, don't paraphrase
        )


# Module-level functions
async def generate_daily_summary():
    """Scheduled daily summary generation."""
    agent = DataAgent()
    await agent.update_status("running")

    result = await agent.daily_summary({})

    # Optionally notify admins
    admin_config = await firebase.get_agent("data")
    admin_users = admin_config.get("config", {}).get("admin_users", [])

    for user_id in admin_users:
        await agent.notify_user(user_id, result.get("message", ""))

    await agent.update_status("idle")


async def process_data_task(task: Dict) -> Dict:
    """Process a single data task."""
    agent = DataAgent()
    await agent.update_status("running")

    try:
        result = await agent.process(task)
        await firebase.complete_task(task["id"], result)
    except Exception as e:
        await firebase.fail_task(task["id"], str(e))
        result = {"error": str(e)}

    await agent.update_status("idle")
    return result
```

---

## Part B: Content Agent

### Capabilities

| Capability | Description |
|------------|-------------|
| `write_content` | Generate new content |
| `translate` | Translate between languages |
| `summarize` | Summarize long text |
| `rewrite` | Improve/rewrite text |
| `email_draft` | Draft professional email |

### Implementation

#### Add Content Agent to main.py

```python
# Add to main.py

@app.function(
    image=image,
    secrets=secrets,
    timeout=120,  # 2 minute max per task (execution limit)
    retries=2,    # Retry on failure
)
async def content_agent_task(task: dict):
    """Content Agent - On-demand content generation."""
    from src.agents.content_generator import process_content_task
    return await process_content_task(task)

@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
    timeout=180,  # 3 minute max per batch (execution limit)
    retries=2,
)
async def process_content_queue():
    """Process pending content tasks from queue."""
    from src.services import firebase
    from src.agents.content_generator import process_content_task

    while True:
        task = await firebase.claim_task("content", "content-processor")
        if not task:
            break
        await process_content_task(task)
```

#### Create src/agents/content_generator.py

```python
from typing import Dict, List, Optional
from src.agents.base import BaseAgent
from src.services import firebase, qdrant, embeddings
from src.services.anthropic import get_claude_response

class ContentAgent(BaseAgent):
    """Content Agent - Content generation and transformation."""

    def __init__(self):
        super().__init__("content")

    async def process(self, task: Dict) -> Dict:
        """Process a content task from queue."""
        action = task.get("payload", {}).get("action", "write_content")
        user_id = task.get("payload", {}).get("user_id")

        handlers = {
            "write_content": self.write_content,
            "translate": self.translate,
            "summarize": self.summarize,
            "rewrite": self.rewrite,
            "email_draft": self.email_draft,
        }

        handler = handlers.get(action, self.write_content)
        result = await handler(task.get("payload", {}))

        if user_id and result.get("message"):
            await self.notify_user(user_id, result["message"])

        return result

    async def write_content(self, payload: Dict) -> Dict:
        """Generate new content."""
        topic = payload.get("topic", "")
        style = payload.get("style", "professional")
        length = payload.get("length", "medium")
        context = payload.get("context", "")

        length_guide = {
            "short": "2-3 paragraphs",
            "medium": "4-6 paragraphs",
            "long": "8-10 paragraphs"
        }

        content = await get_claude_response(
            user_message=f"""Write content about: {topic}

Style: {style}
Length: {length_guide.get(length, length)}
Additional context: {context}""",
            system_prompt=f"You are a {style} content writer. Write engaging, well-structured content."
        )

        # Store in Qdrant for future reference
        embedding = embeddings.get_embedding(content[:500])
        await qdrant.store_knowledge(
            source="content_agent",
            topic=topic,
            content=content,
            embedding=embedding
        )

        return {
            "status": "success",
            "content": content,
            "message": f"✍️ Content về '{topic}':\n\n{content}"
        }

    async def translate(self, payload: Dict) -> Dict:
        """Translate text between languages."""
        text = payload.get("text", "")
        source_lang = payload.get("source", "auto")
        target_lang = payload.get("target", "vi")

        if not text:
            return {"error": "No text provided"}

        translation = await get_claude_response(
            user_message=f"""Translate the following text to {target_lang}:

{text}""",
            system_prompt=f"You are a translator. Translate accurately while preserving meaning and tone. Source language: {source_lang}."
        )

        return {
            "status": "success",
            "translation": translation,
            "message": f"🌐 Translation:\n\n{translation}"
        }

    async def summarize(self, payload: Dict) -> Dict:
        """Summarize long text."""
        text = payload.get("text", "")
        length = payload.get("length", "short")  # short, medium, detailed

        if not text:
            return {"error": "No text provided"}

        length_instruction = {
            "short": "1-2 sentences",
            "medium": "1 paragraph",
            "detailed": "3-4 paragraphs with key points"
        }

        summary = await get_claude_response(
            user_message=f"""Summarize the following text in {length_instruction.get(length, length)}:

{text[:10000]}""",
            system_prompt="You are a summarization expert. Extract key information concisely."
        )

        return {
            "status": "success",
            "summary": summary,
            "message": f"📝 Summary:\n\n{summary}"
        }

    async def rewrite(self, payload: Dict) -> Dict:
        """Rewrite/improve text."""
        text = payload.get("text", "")
        tone = payload.get("tone", "professional")
        instruction = payload.get("instruction", "improve clarity and flow")

        if not text:
            return {"error": "No text provided"}

        rewritten = await get_claude_response(
            user_message=f"""Rewrite the following text.

Tone: {tone}
Instruction: {instruction}

Original text:
{text}""",
            system_prompt=f"You are an editor. Improve the text while maintaining the original meaning."
        )

        return {
            "status": "success",
            "rewritten": rewritten,
            "message": f"✨ Rewritten:\n\n{rewritten}"
        }

    async def email_draft(self, payload: Dict) -> Dict:
        """Draft a professional email."""
        recipient = payload.get("recipient", "")
        subject = payload.get("subject", "")
        key_points = payload.get("key_points", [])
        tone = payload.get("tone", "professional")

        email = await get_claude_response(
            user_message=f"""Draft an email:

Recipient: {recipient}
Subject: {subject}
Key points to include: {', '.join(key_points) if isinstance(key_points, list) else key_points}
Tone: {tone}""",
            system_prompt="You are an email writing assistant. Write clear, professional emails."
        )

        return {
            "status": "success",
            "email": email,
            "message": f"📧 Email Draft:\n\n{email}"
        }

    async def notify_user(self, user_id: str, message: str):
        """
        Notify user via Telegram using forward_to_user pattern.

        Uses direct forwarding to prevent "telephone game" data loss
        where supervisor paraphrases responses incorrectly.
        """
        # Use inherited forward_to_user from BaseAgent
        await self.forward_to_user(
            user_id=user_id,
            message=message,
            bypass_supervisor=True  # Send directly, don't paraphrase
        )


# Module-level function
async def process_content_task(task: Dict) -> Dict:
    """Process a single content task."""
    agent = ContentAgent()
    await agent.update_status("running")

    try:
        result = await agent.process(task)
        await firebase.complete_task(task["id"], result)
    except Exception as e:
        await firebase.fail_task(task["id"], str(e))
        result = {"error": str(e)}

    await agent.update_status("idle")
    return result
```

---

## Files to Create

| Path | Action | Description |
|------|--------|-------------|
| `agents/src/agents/data_processor.py` | Create | Data Agent |
| `agents/src/agents/content_generator.py` | Create | Content Agent |

## Todo List

- [ ] Add Data Agent to main.py
- [ ] Create data_processor.py
- [ ] Add Content Agent to main.py
- [ ] Create content_generator.py
- [ ] Configure admin users in Firebase
- [ ] Deploy and test scheduled reports
- [ ] Test content generation tasks
- [ ] Verify Telegram notifications

## Success Criteria

- [ ] Daily summary runs at 8 AM
- [ ] Data analysis tasks complete successfully
- [ ] Content generation produces quality output
- [ ] All notifications delivered to users

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Long content generation | Timeout | Limit token count |
| Claude rate limits | Task failures | Queue with backoff |
| Large data analysis | Memory issues | Chunk data processing |

## Next Steps

After completing this phase:
1. Proceed to Phase 7: Testing & Deployment
2. Full end-to-end testing
