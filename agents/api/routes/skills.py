"""Skill execution and management endpoints.

Provides API for executing skills, listing available skills, and checking task status.
"""
from fastapi import APIRouter, Request, Depends
from typing import Tuple
import structlog
import time


router = APIRouter(prefix="/api", tags=["skills"])
logger = structlog.get_logger()


@router.post("/skill")
async def skill_api(request: Request):
    """II Framework Skill API endpoint.

    Invoke Modal-deployed skills from Claude Code.

    Request body:
    {
        "skill": "planning",
        "task": "Create a plan for user authentication",
        "context": {"project": "my-app"},  # optional
        "mode": "simple"  # simple|routed|orchestrated|chained|evaluated
    }

    Returns:
        Execution result or task ID if queued for local execution
    """
    from src.services.firebase import create_local_task

    # Import locally to avoid circular dependency
    import sys
    main_module = sys.modules.get("main")
    if not main_module:
        import main as main_module

    is_local_skill = main_module.is_local_skill
    notify_task_queued = main_module.notify_task_queued
    execute_skill_simple = main_module.execute_skill_simple

    try:
        payload = await request.json()
        skill_name = payload.get("skill")
        task = payload.get("task", "")
        context = payload.get("context", {})
        mode = payload.get("mode", "simple")
        user_id = context.get("user_id", 0)

        logger.info("skill_api", skill=skill_name, mode=mode, task_len=len(task))

        # Check if local skill - queue to Firebase instead of executing
        if is_local_skill(skill_name):
            task_id = await create_local_task(
                skill=skill_name,
                task=task,
                user_id=user_id
            )

            logger.info("local_skill_queued", skill=skill_name, task_id=task_id)

            # Notify user if we have user_id
            if user_id:
                await notify_task_queued(user_id, skill_name, task_id)

            return {
                "ok": True,
                "queued": True,
                "task_id": task_id,
                "skill": skill_name,
                "message": f"Skill '{skill_name}' queued for local execution"
            }

        start = time.time()

        if mode == "simple":
            # Direct skill execution
            result = await execute_skill_simple(skill_name, task, context)
        elif mode == "routed":
            # Use router to find best skill
            execute_skill_routed = main_module.execute_skill_routed
            result = await execute_skill_routed(task, context)
        elif mode == "orchestrated":
            # Use orchestrator for complex tasks
            execute_skill_orchestrated = main_module.execute_skill_orchestrated
            result = await execute_skill_orchestrated(task, context)
        elif mode == "chained":
            # Execute skill chain
            execute_skill_chained = main_module.execute_skill_chained
            skills = payload.get("skills", [skill_name])
            result = await execute_skill_chained(skills, task)
        elif mode == "evaluated":
            # Execute with quality evaluation
            execute_skill_evaluated = main_module.execute_skill_evaluated
            result = await execute_skill_evaluated(skill_name, task)
        else:
            return {"ok": False, "error": f"Unknown mode: {mode}"}

        duration_ms = int((time.time() - start) * 1000)

        logger.info("skill_complete", skill=skill_name, mode=mode, duration_ms=duration_ms)

        return {
            "ok": True,
            "result": result,
            "skill": skill_name,
            "mode": mode,
            "duration_ms": duration_ms
        }

    except Exception as e:
        logger.error("skill_api_error", error=str(e))
        return {"ok": False, "error": str(e)}


@router.get("/skills")
async def list_skills():
    """List all available skills.

    Returns:
        List of skills with name, description, and deployment type
    """
    from src.skills.registry import get_registry

    registry = get_registry()
    summaries = registry.discover()

    return {
        "ok": True,
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "deployment": s.deployment
            }
            for s in summaries
        ],
        "count": len(summaries)
    }


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get local task status.

    Args:
        task_id: Task identifier

    Returns:
        Task status and result if completed
    """
    from src.services.firebase import get_task_result

    task = await get_task_result(task_id)
    if not task:
        return {"ok": False, "error": "Task not found"}

    return {
        "ok": True,
        "task": {
            "id": task["id"],
            "skill": task.get("skill"),
            "status": task.get("status"),
            "result": task.get("result"),
            "error": task.get("error"),
            "created_at": task.get("created_at"),
            "completed_at": task.get("completed_at")
        }
    }


@router.post("/content")
async def content_api(request: Request):
    """Content Agent HTTP API endpoint.

    Handles content generation tasks.
    """
    try:
        payload = await request.json()
        logger.info("content_api", action=payload.get("action"))

        task = {"type": "content", "payload": payload}

        from src.agents.content_generator import process_content_task
        result = await process_content_task(task)
        return {"ok": True, "result": result}

    except Exception as e:
        logger.error("content_api_error", error=str(e))
        return {"ok": False, "error": str(e)}


@router.post("/webhook/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events with signature verification.

    Security:
        Webhook signature verified by verify_github_webhook dependency
    """
    from api.dependencies import verify_github_webhook

    # Get verified webhook data
    webhook_data = await verify_github_webhook(request)

    try:
        # Unpack verified data
        event_type, payload = webhook_data

        logger.info("github_webhook", event=event_type)

        task = {
            "type": "github",
            "payload": {
                "action": f"handle_{event_type}",
                "event": event_type,
                "data": payload
            }
        }

        from src.agents.github_automation import process_github_task
        result = await process_github_task(task)
        return {"ok": True, "result": result}

    except Exception as e:
        logger.error("github_webhook_error", error=str(e))
        return {"ok": False, "error": str(e)}
