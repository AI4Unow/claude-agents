# Phase 4: Self-Healing & Recovery

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 3](./phase-03-health-monitoring-observability.md)
- Research: [modal-reliability.md](./research/researcher-02-modal-reliability.md)

## Overview

**Priority:** P1 - Resilience
**Status:** Pending
**Effort:** 2h

Implement checkpointing, graceful shutdown handling, state restoration, and dead letter queue for failed tasks.

## Key Insights

1. Modal containers can be preempted (SIGINT)
2. Checkpointing to Volume enables resume
3. Dead letter queue captures unrecoverable failures
4. State restoration on container restart

## Requirements

### Functional
- Periodic checkpoint to Modal Volume ✓ USER VALIDATED: Every 3 iterations
- SIGINT handler for graceful shutdown
- State restoration on agent startup
- Dead letter queue for failed tasks ✓ USER VALIDATED: 30 day retention

### Non-Functional
- Checkpoint write <500ms
- State restoration <1s
- No data loss on preemption

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-HEALING FLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  STARTUP                                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Check for checkpoint file                              │   │
│  │ 2. If exists, restore state                               │   │
│  │ 3. Resume processing from last known state                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  EXECUTION                                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Every N iterations or T seconds:                          │   │
│  │   save_checkpoint(current_state)                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  SHUTDOWN (SIGINT received)                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Set shutdown flag                                      │   │
│  │ 2. Complete current task (if quick)                       │   │
│  │ 3. Save final checkpoint                                  │   │
│  │ 4. Commit volume                                          │   │
│  │ 5. Exit gracefully                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  FAILURE (Unrecoverable)                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Log error details                                      │   │
│  │ 2. Move task to dead letter queue                         │   │
│  │ 3. Create alert                                           │   │
│  │ 4. Continue with next task                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| Path | Action | Description |
|------|--------|-------------|
| `agents/src/utils/checkpoint.py` | Create | Checkpoint save/restore |
| `agents/src/utils/shutdown.py` | Create | SIGINT handler |
| `agents/src/services/firebase.py` | Modify | Dead letter queue |
| `agents/src/agents/base.py` | Modify | Integrate checkpointing |

## Implementation Steps

### 1. Checkpoint Manager (`src/utils/checkpoint.py`)

```python
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict
import structlog

logger = structlog.get_logger()

CHECKPOINT_DIR = Path("/skills/.checkpoints")

@dataclass
class Checkpoint:
    """Agent checkpoint state."""
    agent_id: str
    task_id: Optional[str]
    state: Dict[str, Any]
    iteration: int
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(**data)

class CheckpointManager:
    """Manages agent checkpoints in Modal Volume."""

    def __init__(self, agent_id: str, volume):
        self.agent_id = agent_id
        self.volume = volume
        self.checkpoint_path = CHECKPOINT_DIR / f"{agent_id}.json"

    def save(self, task_id: str, state: dict, iteration: int):
        """Save checkpoint to volume."""
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

        checkpoint = Checkpoint(
            agent_id=self.agent_id,
            task_id=task_id,
            state=state,
            iteration=iteration,
            timestamp=datetime.utcnow().isoformat(),
        )

        self.checkpoint_path.write_text(json.dumps(checkpoint.to_dict()))
        self.volume.commit()

        logger.info("checkpoint_saved",
            agent=self.agent_id,
            task_id=task_id,
            iteration=iteration
        )

    def load(self) -> Optional[Checkpoint]:
        """Load checkpoint if exists."""
        if not self.checkpoint_path.exists():
            return None

        try:
            data = json.loads(self.checkpoint_path.read_text())
            checkpoint = Checkpoint.from_dict(data)
            logger.info("checkpoint_loaded",
                agent=self.agent_id,
                task_id=checkpoint.task_id
            )
            return checkpoint
        except Exception as e:
            logger.warning("checkpoint_load_failed", error=str(e))
            return None

    def clear(self):
        """Clear checkpoint after successful completion."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            self.volume.commit()
            logger.info("checkpoint_cleared", agent=self.agent_id)
```

### 2. Graceful Shutdown Handler (`src/utils/shutdown.py`)

```python
import signal
import asyncio
from typing import Callable, Optional
import structlog

logger = structlog.get_logger()

class ShutdownHandler:
    """Handles graceful shutdown on SIGINT/SIGTERM."""

    def __init__(self):
        self.shutdown_requested = False
        self.cleanup_callback: Optional[Callable] = None
        self._setup_handlers()

    def _setup_handlers(self):
        """Register signal handlers."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signal."""
        logger.info("shutdown_signal_received", signal=signum)
        self.shutdown_requested = True

        if self.cleanup_callback:
            try:
                # Run cleanup synchronously
                if asyncio.iscoroutinefunction(self.cleanup_callback):
                    asyncio.get_event_loop().run_until_complete(
                        self.cleanup_callback()
                    )
                else:
                    self.cleanup_callback()
            except Exception as e:
                logger.error("cleanup_failed", error=str(e))

    def set_cleanup(self, callback: Callable):
        """Set cleanup callback to run on shutdown."""
        self.cleanup_callback = callback

    def should_shutdown(self) -> bool:
        """Check if shutdown was requested."""
        return self.shutdown_requested

# Global instance
_shutdown_handler: Optional[ShutdownHandler] = None

def get_shutdown_handler() -> ShutdownHandler:
    global _shutdown_handler
    if _shutdown_handler is None:
        _shutdown_handler = ShutdownHandler()
    return _shutdown_handler
```

### 3. Dead Letter Queue (`src/services/firebase.py`)

```python
async def move_to_dead_letter(
    task_id: str,
    task_data: dict,
    error: str,
    agent_id: str
):
    """Move failed task to dead letter queue."""
    db.collection("dead_letter_queue").add({
        "original_task_id": task_id,
        "task_data": task_data,
        "error": error,
        "agent_id": agent_id,
        "failed_at": firestore.SERVER_TIMESTAMP,
        "retry_count": task_data.get("retry_count", 0),
        "status": "failed",
    })

    # Update original task status
    db.collection("tasks").document(task_id).update({
        "status": "dead_lettered",
        "error": error,
    })

    logger.error("task_dead_lettered",
        task_id=task_id,
        agent=agent_id,
        error=error
    )

async def get_dead_letter_tasks(limit: int = 10) -> list:
    """Get tasks from dead letter queue for manual review."""
    docs = db.collection("dead_letter_queue") \
        .where("status", "==", "failed") \
        .order_by("failed_at", direction=firestore.Query.DESCENDING) \
        .limit(limit) \
        .stream()
    return [doc.to_dict() | {"id": doc.id} for doc in docs]

async def retry_dead_letter_task(dlq_id: str) -> str:
    """Retry a dead letter task - creates new task."""
    dlq_doc = db.collection("dead_letter_queue").document(dlq_id).get()
    if not dlq_doc.exists:
        raise ValueError(f"DLQ task not found: {dlq_id}")

    dlq_data = dlq_doc.to_dict()

    # Create new task with incremented retry count
    new_task = db.collection("tasks").add({
        **dlq_data["task_data"],
        "retry_count": dlq_data["retry_count"] + 1,
        "status": "pending",
        "created_at": firestore.SERVER_TIMESTAMP,
        "source": f"dlq_retry:{dlq_id}",
    })

    # Mark DLQ entry as retried
    db.collection("dead_letter_queue").document(dlq_id).update({
        "status": "retried",
        "retried_at": firestore.SERVER_TIMESTAMP,
        "new_task_id": new_task.id,
    })

    return new_task.id
```

### 4. Integrate into BaseAgent

```python
from src.utils.checkpoint import CheckpointManager
from src.utils.shutdown import get_shutdown_handler

class BaseAgent:
    def __init__(self, agent_id: str, volume):
        ...
        self.checkpoint = CheckpointManager(agent_id, volume)
        self.shutdown = get_shutdown_handler()
        self.shutdown.set_cleanup(self._on_shutdown)

    async def run(self, task: dict) -> dict:
        """Run with checkpointing and graceful shutdown."""
        task_id = task.get("id", "unknown")

        # Try to restore from checkpoint
        saved = self.checkpoint.load()
        if saved and saved.task_id == task_id:
            self.logger.info("resuming_from_checkpoint",
                iteration=saved.iteration
            )
            state = saved.state
            start_iteration = saved.iteration
        else:
            state = {}
            start_iteration = 0

        # Process with periodic checkpointing
        for i in range(start_iteration, self.max_iterations):
            if self.shutdown.should_shutdown():
                self.logger.info("shutdown_requested, saving state")
                self.checkpoint.save(task_id, state, i)
                raise SystemExit("Graceful shutdown")

            # Process iteration
            state = await self._process_iteration(task, state, i)

            # Checkpoint every 3 iterations
            if i % 3 == 0:
                self.checkpoint.save(task_id, state, i)

        # Success - clear checkpoint
        self.checkpoint.clear()
        return state

    async def _on_shutdown(self):
        """Cleanup on shutdown."""
        self.logger.info("running_shutdown_cleanup")
        # Any final cleanup
```

## Todo List

- [ ] Create `src/utils/checkpoint.py`
- [ ] Create `src/utils/shutdown.py`
- [ ] Add dead letter queue to Firebase
- [ ] Integrate checkpointing into BaseAgent
- [ ] Add DLQ retry endpoint
- [ ] Write tests for checkpoint save/restore
- [ ] Write tests for shutdown handler

## Success Criteria

- [ ] Checkpoint saves in <500ms
- [ ] State restores correctly after restart
- [ ] SIGINT triggers graceful shutdown
- [ ] Failed tasks appear in dead letter queue
- [ ] DLQ tasks can be retried

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Checkpoint corruption | Lost state | Validate on load |
| Volume commit slow | Delay shutdown | Async commit |
| DLQ grows unbounded | Storage costs | Add retention policy |

## Security Considerations

- Don't checkpoint sensitive data unencrypted
- Sanitize error messages in DLQ
- Limit DLQ access to admins

## Next Steps

→ Integration testing with full reliability stack
→ Update parent plan phases with reliability integration
