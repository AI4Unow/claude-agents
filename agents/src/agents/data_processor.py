"""Data Agent - Analytics and reporting.

Generates reports, analyzes data, and produces daily summaries.
Uses Z.AI GLM for LLM operations.
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import structlog

from src.agents.base import BaseAgent
from src.services.llm import get_llm_client

logger = structlog.get_logger()


class DataAgent(BaseAgent):
    """Data Agent - Analytics and reporting."""

    def __init__(self):
        super().__init__("data")

    async def process(self, task: Dict) -> Dict:
        """Process a data task from queue."""
        action = task.get("payload", {}).get("action", "")

        handlers = {
            "daily_summary": self.daily_summary,
            "analyze_data": self.analyze_data,
            "generate_report": self.generate_report,
        }

        handler = handlers.get(action, self.handle_unknown)
        result = await handler(task.get("payload", {}))

        return result

    async def daily_summary(self, payload: Dict) -> Dict:
        """Generate daily activity summary."""
        try:
            from src.services.firebase import get_db
            db = get_db()

            # Get logs from last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)

            # Count tasks by status
            tasks_ref = db.collection("tasks")
            all_tasks = list(tasks_ref.stream())

            task_stats = {
                "total": len(all_tasks),
                "done": len([t for t in all_tasks if t.to_dict().get("status") == "done"]),
                "failed": len([t for t in all_tasks if t.to_dict().get("status") == "failed"]),
                "pending": len([t for t in all_tasks if t.to_dict().get("status") == "pending"]),
            }

            # Generate summary with LLM
            prompt = f"""Generate a brief daily activity summary based on:

Task Statistics:
- Total tasks: {task_stats['total']}
- Completed: {task_stats['done']}
- Failed: {task_stats['failed']}
- Pending: {task_stats['pending']}

Date: {datetime.utcnow().strftime('%Y-%m-%d')}

Provide a 2-3 sentence summary highlighting key metrics and any concerns."""

            summary = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "summary": summary,
                "stats": task_stats,
                "message": f"📊 Daily Summary:\n\n{summary}"
            }
        except Exception as e:
            logger.error("daily_summary_error", error=str(e))
            return {"error": str(e), "message": f"❌ Error: {str(e)}"}

    async def analyze_data(self, payload: Dict) -> Dict:
        """Analyze provided data."""
        data = payload.get("data", "")
        question = payload.get("question", "Analyze this data")

        if not data:
            return {"error": "No data provided"}

        prompt = f"""Analyze this data and answer the question.

Data:
{data[:5000]}

Question: {question}

Provide clear insights with actionable recommendations."""

        try:
            analysis = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "analysis": analysis,
                "message": f"📈 Data Analysis:\n\n{analysis}"
            }
        except Exception as e:
            logger.error("analyze_data_error", error=str(e))
            return {"error": str(e)}

    async def generate_report(self, payload: Dict) -> Dict:
        """Generate a formatted report."""
        topic = payload.get("topic", "")
        data = payload.get("data", {})
        format_type = payload.get("format", "markdown")

        prompt = f"""Generate a {format_type} report about: {topic}

Data: {json.dumps(data)[:3000] if isinstance(data, dict) else str(data)[:3000]}

Create a well-structured report with sections, key findings, and recommendations."""

        try:
            report = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "report": report,
                "message": f"📄 Report: {topic}\n\n{report[:2000]}..."
            }
        except Exception as e:
            logger.error("generate_report_error", error=str(e))
            return {"error": str(e)}

    async def handle_unknown(self, payload: Dict) -> Dict:
        return {"error": "Unknown action"}


# Module-level functions
async def process_data_task(task: Dict) -> Dict:
    """Process a single data task."""
    agent = DataAgent()

    try:
        result = await agent.process(task)
        return result
    except Exception as e:
        logger.error("data_task_error", error=str(e))
        return {"error": str(e)}
