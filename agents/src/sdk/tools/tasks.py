"""SmartTask CRUD tools for SDK."""

from claude_agents import tool
from typing import List, Dict, Optional
from datetime import datetime
import structlog

from src.services.firebase.pkm import (
    create_smart_task,
    get_smart_task,
    update_smart_task,
    delete_smart_task,
    list_smart_tasks,
    get_due_tasks,
    SmartTask
)
from src.core.nlp_parser import parse_task, format_task_summary
from src.utils.logging import get_logger

logger = get_logger()


def _task_to_dict(task: SmartTask) -> Dict:
    """Convert SmartTask to dict for SDK response."""
    return {
        "id": task.id,
        "content": task.content,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "due_time": task.due_time.isoformat() if task.due_time else None,
        "tags": task.tags,
        "project": task.project,
        "context": task.context,
        "recurrence": task.recurrence,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@tool
async def task_create(
    user_id: int,
    content: str,
    due_date: Optional[str] = None,
    priority: Optional[str] = None,
    context: Optional[str] = None,
    use_nlp: bool = False,
) -> Dict:
    """Create a new task for user.

    Args:
        user_id: User's Telegram ID
        content: Task description (or natural language if use_nlp=True)
        due_date: Due date in YYYY-MM-DD format (optional)
        priority: Priority level (p1, p2, p3, p4, optional)
        context: Context tag (@home, @work, @errands, optional)
        use_nlp: Use NLP parser to extract fields from content (default: False)

    Returns:
        Task ID and status with created task details
    """
    try:
        # Use NLP parser if requested
        if use_nlp:
            parsed = await parse_task(content, datetime.now())
            task = await create_smart_task(
                user_id=user_id,
                content=parsed.content,
                priority=parsed.priority or priority,
                context=parsed.context or context,
                due_date=parsed.due_date,
                due_time=parsed.due_time,
                recurrence=parsed.recurrence,
                auto_created=True,
                confidence_score=parsed.confidence
            )
        else:
            # Direct creation
            task_kwargs = {}
            if due_date:
                task_kwargs["due_date"] = datetime.fromisoformat(due_date)
            if priority:
                task_kwargs["priority"] = priority
            if context:
                task_kwargs["context"] = context

            task = await create_smart_task(
                user_id=user_id,
                content=content,
                **task_kwargs
            )

        logger.info("task_created", user_id=user_id, task_id=task.id)

        return {
            "id": task.id,
            "status": "created",
            "task": _task_to_dict(task)
        }

    except Exception as e:
        logger.error("task_create_error", user_id=user_id, error=str(e))
        return {
            "status": "error",
            "message": f"Failed to create task: {str(e)}"
        }


@tool
async def task_list(
    user_id: int,
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict:
    """List user's tasks.

    Args:
        user_id: User's Telegram ID
        status: Filter by status (inbox, active, done, archived; optional)
        limit: Max results to return (default: 20)

    Returns:
        List of tasks with id, content, due date, etc.
    """
    try:
        tasks = await list_smart_tasks(user_id, status=status, limit=limit)

        return {
            "status": "success",
            "count": len(tasks),
            "tasks": [_task_to_dict(t) for t in tasks]
        }

    except Exception as e:
        logger.error("task_list_error", user_id=user_id, error=str(e))
        return {
            "status": "error",
            "message": f"Failed to list tasks: {str(e)}",
            "tasks": []
        }


@tool
async def task_update(
    user_id: int,
    task_id: str,
    content: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
) -> Dict:
    """Update task fields.

    Args:
        user_id: User's Telegram ID
        task_id: Task ID to update
        content: New content (optional)
        status: New status (inbox, active, done, archived; optional)
        priority: New priority (p1, p2, p3, p4; optional)
        due_date: New due date in YYYY-MM-DD format (optional)

    Returns:
        Task ID and updated task details
    """
    try:
        updates = {}
        if content:
            updates["content"] = content
        if status:
            updates["status"] = status
        if priority:
            updates["priority"] = priority
        if due_date:
            updates["due_date"] = datetime.fromisoformat(due_date)

        task = await update_smart_task(user_id, task_id, **updates)

        if not task:
            return {
                "status": "error",
                "message": f"Task {task_id} not found"
            }

        logger.info("task_updated", user_id=user_id, task_id=task_id)

        return {
            "id": task.id,
            "status": "updated",
            "task": _task_to_dict(task)
        }

    except Exception as e:
        logger.error("task_update_error", user_id=user_id, task_id=task_id, error=str(e))
        return {
            "status": "error",
            "message": f"Failed to update task: {str(e)}"
        }


@tool
async def task_complete(
    user_id: int,
    task_id: str
) -> Dict:
    """Mark task as completed.

    Args:
        user_id: User's Telegram ID
        task_id: Task ID to complete

    Returns:
        Task ID and new status
    """
    try:
        task = await update_smart_task(user_id, task_id, status="done")

        if not task:
            return {
                "status": "error",
                "message": f"Task {task_id} not found"
            }

        logger.info("task_completed", user_id=user_id, task_id=task_id)

        return {
            "id": task.id,
            "status": "completed",
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }

    except Exception as e:
        logger.error("task_complete_error", user_id=user_id, task_id=task_id, error=str(e))
        return {
            "status": "error",
            "message": f"Failed to complete task: {str(e)}"
        }


@tool
async def task_delete(
    user_id: int,
    task_id: str
) -> Dict:
    """Delete a task.

    Args:
        user_id: User's Telegram ID
        task_id: Task ID to delete

    Returns:
        Deletion status
    """
    try:
        deleted = await delete_smart_task(user_id, task_id)

        if not deleted:
            return {
                "status": "error",
                "message": f"Task {task_id} not found"
            }

        logger.info("task_deleted", user_id=user_id, task_id=task_id)

        return {
            "id": task_id,
            "status": "deleted"
        }

    except Exception as e:
        logger.error("task_delete_error", user_id=user_id, task_id=task_id, error=str(e))
        return {
            "status": "error",
            "message": f"Failed to delete task: {str(e)}"
        }


@tool
async def task_get_due(
    user_id: int,
    limit: int = 10,
) -> Dict:
    """Get tasks that are due now.

    Args:
        user_id: User's Telegram ID
        limit: Max results to return (default: 10)

    Returns:
        List of due tasks
    """
    try:
        tasks = await get_due_tasks(user_id, limit=limit)

        return {
            "status": "success",
            "count": len(tasks),
            "tasks": [_task_to_dict(t) for t in tasks]
        }

    except Exception as e:
        logger.error("task_get_due_error", user_id=user_id, error=str(e))
        return {
            "status": "error",
            "message": f"Failed to get due tasks: {str(e)}",
            "tasks": []
        }
