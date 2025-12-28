"""Content Agent - Content generation and transformation.

Generates, translates, summarizes, and rewrites content.
Uses Z.AI GLM for LLM operations.
"""
from typing import Dict, List, Optional

from src.utils.logging import get_logger
from src.agents.base import BaseAgent

logger = get_logger()


class ContentAgent(BaseAgent):
    """Content Agent - Content generation and transformation."""

    def __init__(self):
        super().__init__("content")

    async def process(self, task: Dict) -> Dict:
        """Process a content task from queue."""
        action = task.get("payload", {}).get("action", "write_content")

        handlers = {
            "write_content": self.write_content,
            "translate": self.translate,
            "summarize": self.summarize,
            "rewrite": self.rewrite,
            "email_draft": self.email_draft,
        }

        handler = handlers.get(action, self.write_content)
        result = await handler(task.get("payload", {}))

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

        prompt = f"""Write content about: {topic}

Style: {style}
Length: {length_guide.get(length, length)}
Additional context: {context}

Write engaging, well-structured content."""

        try:
            content = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "content": content,
                "message": f"✍️ Content about '{topic}':\n\n{content}"
            }
        except Exception as e:
            logger.error("write_content_error", error=str(e))
            return {"error": str(e)}

    async def translate(self, payload: Dict) -> Dict:
        """Translate text between languages."""
        text = payload.get("text", "")
        source_lang = payload.get("source", "auto")
        target_lang = payload.get("target", "vi")

        if not text:
            return {"error": "No text provided"}

        prompt = f"""Translate the following text to {target_lang}:

{text}

Translate accurately while preserving meaning and tone. Source language: {source_lang}."""

        try:
            translation = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "translation": translation,
                "message": f"🌐 Translation:\n\n{translation}"
            }
        except Exception as e:
            logger.error("translate_error", error=str(e))
            return {"error": str(e)}

    async def summarize(self, payload: Dict) -> Dict:
        """Summarize long text."""
        text = payload.get("text", "")
        length = payload.get("length", "short")

        if not text:
            return {"error": "No text provided"}

        length_instruction = {
            "short": "1-2 sentences",
            "medium": "1 paragraph",
            "detailed": "3-4 paragraphs with key points"
        }

        prompt = f"""Summarize the following text in {length_instruction.get(length, length)}:

{text[:10000]}

Extract key information concisely."""

        try:
            summary = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "summary": summary,
                "message": f"📝 Summary:\n\n{summary}"
            }
        except Exception as e:
            logger.error("summarize_error", error=str(e))
            return {"error": str(e)}

    async def rewrite(self, payload: Dict) -> Dict:
        """Rewrite/improve text."""
        text = payload.get("text", "")
        tone = payload.get("tone", "professional")
        instruction = payload.get("instruction", "improve clarity and flow")

        if not text:
            return {"error": "No text provided"}

        prompt = f"""Rewrite the following text.

Tone: {tone}
Instruction: {instruction}

Original text:
{text}

Improve the text while maintaining the original meaning."""

        try:
            rewritten = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "rewritten": rewritten,
                "message": f"✨ Rewritten:\n\n{rewritten}"
            }
        except Exception as e:
            logger.error("rewrite_error", error=str(e))
            return {"error": str(e)}

    async def email_draft(self, payload: Dict) -> Dict:
        """Draft a professional email."""
        recipient = payload.get("recipient", "")
        subject = payload.get("subject", "")
        key_points = payload.get("key_points", [])
        tone = payload.get("tone", "professional")

        prompt = f"""Draft an email:

Recipient: {recipient}
Subject: {subject}
Key points to include: {', '.join(key_points) if isinstance(key_points, list) else key_points}
Tone: {tone}

Write a clear, professional email."""

        try:
            email = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "email": email,
                "message": f"📧 Email Draft:\n\n{email}"
            }
        except Exception as e:
            logger.error("email_draft_error", error=str(e))
            return {"error": str(e)}


# Module-level function
async def process_content_task(task: Dict) -> Dict:
    """Process a single content task."""
    agent = ContentAgent()

    try:
        result = await agent.process(task)
        return result
    except Exception as e:
        logger.error("content_task_error", error=str(e))
        return {"error": str(e)}
