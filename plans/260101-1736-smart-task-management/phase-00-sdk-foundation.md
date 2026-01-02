# Phase 0: SDK Foundation

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: None (first phase)
- **Research**: [SDK Adoption Brainstorm](../reports/brainstorm-260101-1847-claude-agents-sdk-adoption.md), [Full Migration Brainstorm](../reports/brainstorm-260101-1901-full-sdk-migration.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2026-01-01 |
| Priority | P1 |
| Effort | 18h |
| Status | pending |

**Scope Expanded:** Full SDK migration for ALL agentic functionalities (not just Task Management). Replaces `agentic.py`, `llm.py`, and old tool registry with SDK primitives.

## Key Insights

1. **SDK replaces ~550 lines** of custom loop management across all agents
2. **Native Hooks** = purpose-built trust rules, tracing, circuit breakers
3. **Native Checkpointing** = undo capability without custom L1/L2 queue
4. **Subagent pattern** = clean separation for NLP/Timing/Sync
5. **MCP support** = future extensibility for tool servers
6. **Unified architecture** = Telegram, GitHub, Content agents all use same SDK

## Requirements

1. SDK agent configuration with Modal compatibility
2. Trust rules migrated to PreToolUse hooks
3. ALL existing tools migrated to `@tool` decorators
4. Tracing integration via PostToolUse hooks
5. Circuit breaker integration via PreToolUse hooks
6. Self-improvement triggers via PostToolUse hooks
7. Checkpointing enabled for undo capability
8. Telegram chat agent fully migrated
9. GitHub agent migrated
10. Content agent migrated
11. Backward-compatible API during transition

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   PHASE 0 ARCHITECTURE (FULL MIGRATION)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Claude Agents SDK                            │   │
│  │                                                                    │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │   │
│  │  │   Agent Loop   │  │     Hooks      │  │  Checkpoints   │      │   │
│  │  │                │  │                │  │                │      │   │
│  │  │ • think        │  │ • PreToolUse   │  │ • save()       │      │   │
│  │  │ • tool call    │  │ • PostToolUse  │  │ • restore()    │      │   │
│  │  │ • verify       │  │ • trust rules  │  │ • list()       │      │   │
│  │  │ • repeat       │  │ • tracing      │  │ • native undo  │      │   │
│  │  │                │  │ • circuits     │  │                │      │   │
│  │  │                │  │ • improvement  │  │                │      │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘      │   │
│  │                              │                                     │   │
│  │                              ▼                                     │   │
│  │  ┌────────────────────────────────────────────────────────────┐  │   │
│  │  │                     Tool Registry                           │  │   │
│  │  │                                                              │  │   │
│  │  │  EXISTING TOOLS (migrated):                                 │  │   │
│  │  │  @tool web_search()      @tool search_memory()              │  │   │
│  │  │  @tool run_python()      @tool get_datetime()               │  │   │
│  │  │  @tool read_webpage()    @tool gemini_*()                   │  │   │
│  │  │                                                              │  │   │
│  │  │  NEW TOOLS (Task Management):                               │  │   │
│  │  │  @tool task_create()     @tool calendar_read()              │  │   │
│  │  │  @tool task_update()     @tool calendar_write()             │  │   │
│  │  │  @tool task_delete()     @tool nlp_parse()                  │  │   │
│  │  │  @tool task_list()       @tool smart_timing()               │  │   │
│  │  └────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Modal Container                              │   │
│  │                                                                    │   │
│  │  Agents Using SDK:                                                │   │
│  │  ├── Telegram Chat Agent (primary)                               │   │
│  │  ├── GitHub Agent (cron)                                         │   │
│  │  └── Content Agent (on-demand)                                   │   │
│  │                                                                    │   │
│  │  Unchanged:                                                       │   │
│  │  ├── Circuit Breakers (wrap SDK calls)                           │   │
│  │  ├── StateManager (Firebase state)                               │   │
│  │  ├── Command Router (Telegram-specific)                          │   │
│  │  └── Cron Jobs (simple, not agentic)                            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Hook Architecture

```
Request → SDK Agent
             │
             ├── PreToolUse Hooks (in order)
             │   ├── CircuitBreakerHook     # Check if service open
             │   ├── TrustRulesHook         # Check if action allowed
             │   └── TierLimitHook          # Check iteration budget
             │
             ├── Tool Execution
             │
             └── PostToolUse Hooks (in order)
                 ├── TracingHook            # Log to TraceContext
                 ├── ImprovementHook        # Trigger on errors
                 └── NotificationHook       # Auto-notify if configured
```

## Related Files

| File | Action | Purpose |
|------|--------|---------|
| `src/sdk/__init__.py` | Create | Package exports |
| `src/sdk/agent.py` | Create | Main SDK agent configuration |
| `src/sdk/config.py` | Create | Tier limits, permission modes |
| `src/sdk/hooks/__init__.py` | Create | Hooks package |
| `src/sdk/hooks/trust_rules.py` | Create | PreToolUse trust checks |
| `src/sdk/hooks/circuits.py` | Create | PreToolUse circuit breaker checks |
| `src/sdk/hooks/tracing.py` | Create | PostToolUse TraceContext integration |
| `src/sdk/hooks/improvement.py` | Create | PostToolUse self-improvement trigger |
| `src/sdk/tools/__init__.py` | Create | Tools package, get_all_tools() |
| `src/sdk/tools/web_search.py` | Create | @tool web_search (Exa + Tavily) |
| `src/sdk/tools/memory.py` | Create | @tool search_memory (Qdrant) |
| `src/sdk/tools/code_exec.py` | Create | @tool run_python |
| `src/sdk/tools/datetime.py` | Create | @tool get_datetime |
| `src/sdk/tools/gemini.py` | Create | @tool gemini_* (vision, grounding) |
| `src/sdk/tools/task_tools.py` | Create | @tool task_* (SmartTask CRUD) |
| `src/sdk/tools/calendar_tools.py` | Create | @tool calendar_* (Phase 3 stubs) |
| `src/sdk/tools/nlp_tools.py` | Create | @tool nlp_parse |
| `api/routes/telegram.py` | Modify | Use SDK agent instead of agentic.py |
| `src/agents/github.py` | Modify | Use SDK agent |
| `src/agents/content.py` | Modify | Use SDK agent |
| `src/services/agentic.py` | Delete | Replaced by SDK |
| `src/services/llm.py` | Delete | Replaced by SDK |
| `src/tools/` | Delete | Moved to src/sdk/tools/ |
| `requirements.txt` | Modify | Add `anthropic-tools` SDK |

## Implementation Steps

### Phase A: SDK Foundation (4h)

#### A.1. Package Setup (1h)

Create package structure and dependencies:

```bash
mkdir -p src/sdk/{hooks,tools}
touch src/sdk/__init__.py src/sdk/hooks/__init__.py src/sdk/tools/__init__.py
```

Add SDK to requirements:
```
# requirements.txt
anthropic>=0.40.0
claude-agents-sdk>=0.5.0
```

Create `src/sdk/__init__.py`:
```python
"""Claude Agents SDK integration for ai4u.now."""

from .agent import create_agent, run_agent
from .config import AgentConfig, TierLimits

__all__ = ["create_agent", "run_agent", "AgentConfig", "TierLimits"]
```

#### A.2. Agent Core (2h)

Create `src/sdk/agent.py`:
```python
"""Main SDK agent configuration."""

from anthropic import Anthropic
from claude_agents import Agent
from typing import List, Optional, Callable
import structlog

from .config import AgentConfig, TierLimits
from .hooks import get_all_hooks
from .tools import get_all_tools
from src.core.resilience import CircuitBreakerManager

logger = structlog.get_logger()


def create_agent(
    user_id: int,
    tier: str = "user",
    config: Optional[AgentConfig] = None,
    tools: Optional[List[Callable]] = None,
    circuit_manager: Optional[CircuitBreakerManager] = None,
) -> Agent:
    """Create SDK agent for user with tier-appropriate limits.

    Args:
        user_id: Telegram user ID
        tier: User tier (guest, user, developer, admin)
        config: Optional agent config override
        tools: Optional tool list override
        circuit_manager: Circuit breaker manager for PreToolUse

    Returns:
        Configured Agent instance
    """
    config = config or AgentConfig.for_tier(tier)

    # Get tier-appropriate iteration limits
    limits = TierLimits.for_tier(tier)

    # Collect all hooks
    hooks = get_all_hooks(
        user_id=user_id,
        config=config,
        circuit_manager=circuit_manager,
    )

    # Get tools (existing + new)
    all_tools = tools or get_all_tools()

    agent = Agent(
        model=config.model,
        tools=all_tools,
        hooks=hooks,
        max_iterations=limits.max_iterations,
        system_prompt=_build_system_prompt(user_id, tier),
    )

    return agent


async def run_agent(
    agent: Agent,
    message: str,
    context: Optional[dict] = None,
) -> str:
    """Run agent with message.

    Args:
        agent: Configured Agent
        message: User message
        context: Optional context (tasks, calendar, etc.)

    Returns:
        Agent response
    """
    prompt = message
    if context:
        prompt = f"Context: {context}\n\nUser: {message}"

    try:
        result = await agent.run(prompt)
        return result.content
    except Exception as e:
        logger.error("agent_run_failed", error=str(e))
        raise


def _build_system_prompt(user_id: int, tier: str) -> str:
    """Build system prompt with user context."""
    return f"""You are ai4u.now, a smart personal assistant.
User ID: {user_id} | Tier: {tier}

Capabilities: Task management, calendar sync, web search, memory, code execution.
Trust rules enforce permission checks before tool execution."""
```

#### A.3. Config Module (1h)

Create `src/sdk/config.py`:
```python
"""SDK configuration for tiers and permissions."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TierLimits:
    max_iterations: int
    max_tools_per_turn: int

    @classmethod
    def for_tier(cls, tier: str) -> "TierLimits":
        limits = {
            "guest": cls(max_iterations=3, max_tools_per_turn=2),
            "user": cls(max_iterations=10, max_tools_per_turn=5),
            "developer": cls(max_iterations=25, max_tools_per_turn=10),
            "admin": cls(max_iterations=50, max_tools_per_turn=20),
        }
        return limits.get(tier, limits["user"])


@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-20250514"
    checkpoint_enabled: bool = True

    @classmethod
    def for_tier(cls, tier: str) -> "AgentConfig":
        return cls()  # Same config, different limits via TierLimits
```

### Phase B: Hooks Migration (4h)

#### B.1. Circuit Breaker Hook (1h)

Create `src/sdk/hooks/circuits.py`:
```python
"""Circuit breaker PreToolUse hook."""

from claude_agents import Hook, PreToolUseResult
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

# Tool → Circuit breaker mapping
TOOL_CIRCUITS = {
    "web_search": ["exa", "tavily"],
    "search_memory": ["qdrant"],
    "gemini_vision": ["gemini"],
    "gemini_grounding": ["gemini"],
}


class CircuitBreakerHook(Hook):
    """Block tool execution if circuit is open."""

    def __init__(self, circuit_manager):
        self.circuit_manager = circuit_manager

    async def pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> PreToolUseResult:
        circuits = TOOL_CIRCUITS.get(tool_name, [])

        for circuit_name in circuits:
            if not self.circuit_manager.is_closed(circuit_name):
                logger.warning("circuit_open", tool=tool_name, circuit=circuit_name)
                return PreToolUseResult(
                    allow=False,
                    message=f"Service {circuit_name} temporarily unavailable",
                )

        return PreToolUseResult(allow=True)
```

#### B.2. Trust Rules Hook (1.5h)

Create `src/sdk/hooks/trust_rules.py`:
```python
"""Trust rules as PreToolUse hook."""

from claude_agents import Hook, PreToolUseResult, PostToolUseResult
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class TrustLevel(Enum):
    AUTO_SILENT = "auto_silent"
    AUTO_NOTIFY = "auto_notify"
    CONFIRM = "confirm"


@dataclass
class ActionRule:
    trust: TrustLevel
    template: Optional[str] = None


DEFAULT_RULES = {
    "task_create": ActionRule(TrustLevel.AUTO_NOTIFY, "Created: {content}"),
    "task_update": ActionRule(TrustLevel.AUTO_NOTIFY, "Updated: {task_id}"),
    "task_delete": ActionRule(TrustLevel.CONFIRM),
    "calendar_write": ActionRule(TrustLevel.CONFIRM),
    "web_search": ActionRule(TrustLevel.AUTO_SILENT),
    "search_memory": ActionRule(TrustLevel.AUTO_SILENT),
}


class TrustRulesHook(Hook):
    """Enforce trust rules before tool execution."""

    def __init__(self, user_id: int, rules: Dict[str, ActionRule] = None):
        self.user_id = user_id
        self.rules = rules or DEFAULT_RULES

    async def pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> PreToolUseResult:
        rule = self.rules.get(tool_name, ActionRule(TrustLevel.CONFIRM))

        if rule.trust == TrustLevel.CONFIRM:
            return PreToolUseResult(
                allow=False,
                message=f"Confirm {tool_name}? Reply 'yes' to proceed.",
            )

        return PreToolUseResult(allow=True)

    async def post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> PostToolUseResult:
        rule = self.rules.get(tool_name)
        if rule and rule.trust == TrustLevel.AUTO_NOTIFY and rule.template:
            msg = rule.template.format(**tool_input)
            await self._notify(msg)
        return PostToolUseResult()

    async def _notify(self, message: str):
        from src.services.telegram import send_message
        await send_message(self.user_id, f"[ai4u.now] {message}")
```

#### B.3. Tracing Hook (1h)

Create `src/sdk/hooks/tracing.py`:
```python
"""Tracing integration as PostToolUse hook."""

from claude_agents import Hook, PostToolUseResult
from typing import Dict, Any
import time
import structlog

from src.core.trace import TraceContext

logger = structlog.get_logger()


class TracingHook(Hook):
    """Log tool calls to TraceContext."""

    def __init__(self, trace_context: TraceContext):
        self.trace = trace_context
        self._start_times: Dict[str, float] = {}

    async def pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ):
        self._start_times[tool_name] = time.time()

    async def post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> PostToolUseResult:
        duration = time.time() - self._start_times.pop(tool_name, time.time())

        self.trace.add_tool_call(
            name=tool_name,
            input_summary=str(tool_input)[:200],
            duration_ms=int(duration * 1000),
            success=not isinstance(tool_output, Exception),
        )

        return PostToolUseResult()
```

#### B.4. Improvement Hook (0.5h)

Create `src/sdk/hooks/improvement.py`:
```python
"""Self-improvement trigger as PostToolUse hook."""

from claude_agents import Hook, PostToolUseResult
from typing import Dict, Any
import structlog

from src.core.improvement import trigger_improvement

logger = structlog.get_logger()


class ImprovementHook(Hook):
    """Trigger self-improvement on tool errors."""

    def __init__(self, skill_name: str = None):
        self.skill_name = skill_name

    async def post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> PostToolUseResult:
        if isinstance(tool_output, Exception):
            await trigger_improvement(
                skill=self.skill_name or tool_name,
                error=str(tool_output),
                context={"tool": tool_name, "input": tool_input},
            )
            logger.info("improvement_triggered", tool=tool_name)

        return PostToolUseResult()
```

### Phase C: Tools Migration (4h)

#### C.1. Web Search Tool (1h)

Create `src/sdk/tools/web_search.py`:
```python
"""Web search tool (migrated from src/tools/web_search.py)."""

from claude_agents import tool
from typing import Optional, List
import structlog

from src.core.resilience import get_circuit_manager

logger = structlog.get_logger()


@tool
async def web_search(
    query: str,
    max_results: int = 5,
    search_type: str = "general",
) -> List[dict]:
    """Search the web for information.

    Args:
        query: Search query
        max_results: Maximum results to return
        search_type: Type of search (general, news, academic)

    Returns:
        List of search results with title, url, snippet
    """
    circuit = get_circuit_manager()

    # Try Exa first, fallback to Tavily
    if circuit.is_closed("exa"):
        try:
            return await _search_exa(query, max_results)
        except Exception as e:
            circuit.record_failure("exa")
            logger.warning("exa_failed", error=str(e))

    if circuit.is_closed("tavily"):
        try:
            return await _search_tavily(query, max_results)
        except Exception as e:
            circuit.record_failure("tavily")
            logger.warning("tavily_failed", error=str(e))

    return [{"error": "Search services unavailable"}]


async def _search_exa(query: str, max_results: int) -> List[dict]:
    # Existing Exa implementation
    from src.services.exa import search as exa_search
    return await exa_search(query, num_results=max_results)


async def _search_tavily(query: str, max_results: int) -> List[dict]:
    # Existing Tavily implementation
    from src.services.tavily import search as tavily_search
    return await tavily_search(query, max_results=max_results)
```

#### C.2. Memory Tool (0.5h)

Create `src/sdk/tools/memory.py`:
```python
"""Memory search tool (migrated from src/tools/memory.py)."""

from claude_agents import tool
from typing import List
import structlog

logger = structlog.get_logger()


@tool
async def search_memory(
    user_id: int,
    query: str,
    limit: int = 5,
) -> List[dict]:
    """Search user's memory/PKM.

    Args:
        user_id: User's Telegram ID
        query: Semantic search query
        limit: Max results

    Returns:
        Matching memories with content and metadata
    """
    from src.services.qdrant import semantic_search

    results = await semantic_search(
        user_id=user_id,
        query=query,
        limit=limit,
    )

    return [
        {"content": r.content, "created": str(r.created_at), "score": r.score}
        for r in results
    ]
```

#### C.3. Code Execution Tool (0.5h)

Create `src/sdk/tools/code_exec.py`:
```python
"""Code execution tool."""

from claude_agents import tool
from typing import Optional
import structlog

logger = structlog.get_logger()


@tool
async def run_python(
    code: str,
    timeout: int = 30,
) -> dict:
    """Execute Python code safely.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds

    Returns:
        Execution result with stdout, stderr, return_value
    """
    from src.services.code_executor import execute_python

    result = await execute_python(code, timeout=timeout)

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "return_value": result.return_value,
        "success": result.success,
    }
```

#### C.4. Datetime Tool (0.25h)

Create `src/sdk/tools/datetime.py`:
```python
"""Datetime utility tool."""

from claude_agents import tool
from datetime import datetime, timezone


@tool
async def get_datetime(
    timezone_name: str = "UTC",
) -> dict:
    """Get current date and time.

    Args:
        timezone_name: Timezone name (default UTC)

    Returns:
        Current datetime info
    """
    import pytz

    tz = pytz.timezone(timezone_name)
    now = datetime.now(tz)

    return {
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "timezone": timezone_name,
    }
```

#### C.5. Gemini Tools (1h)

Create `src/sdk/tools/gemini.py`:
```python
"""Gemini AI tools (vision, grounding, thinking)."""

from claude_agents import tool
from typing import Optional
import structlog

logger = structlog.get_logger()


@tool
async def gemini_vision(
    image_url: str,
    prompt: str,
) -> dict:
    """Analyze image with Gemini Vision.

    Args:
        image_url: URL of image to analyze
        prompt: Analysis prompt

    Returns:
        Vision analysis result
    """
    from src.services.gemini import analyze_image

    result = await analyze_image(image_url, prompt)
    return {"analysis": result}


@tool
async def gemini_grounding(
    query: str,
) -> dict:
    """Web-grounded response from Gemini.

    Args:
        query: Query requiring current information

    Returns:
        Grounded response with sources
    """
    from src.services.gemini import grounded_search

    result = await grounded_search(query)
    return {"response": result.content, "sources": result.sources}


@tool
async def gemini_thinking(
    problem: str,
    thinking_budget: int = 10000,
) -> dict:
    """Deep thinking with Gemini.

    Args:
        problem: Complex problem to analyze
        thinking_budget: Token budget for thinking

    Returns:
        Analysis with reasoning
    """
    from src.services.gemini import deep_think

    result = await deep_think(problem, budget=thinking_budget)
    return {"analysis": result.content, "thinking": result.thinking}
```

#### C.6. Task Management Tools (0.75h)

Create `src/sdk/tools/tasks.py` (SmartTask CRUD for Phase 1):
```python
"""SmartTask CRUD tools."""

from claude_agents import tool
from typing import Optional, List
from datetime import datetime


@tool
async def task_create(
    user_id: int,
    content: str,
    due_date: Optional[str] = None,
    priority: Optional[str] = None,
    context: Optional[str] = None,
) -> dict:
    """Create a new task."""
    from src.services.firebase.pkm import create_smart_task

    task = await create_smart_task(
        user_id=user_id,
        content=content,
        due_date=datetime.strptime(due_date, "%Y-%m-%d").date() if due_date else None,
        priority=priority,
        context=context,
    )
    return {"id": task.id, "status": "created"}


@tool
async def task_list(
    user_id: int,
    status: Optional[str] = None,
    limit: int = 20,
) -> List[dict]:
    """List user's tasks."""
    from src.services.firebase.pkm import list_smart_tasks

    tasks = await list_smart_tasks(user_id, status=status, limit=limit)
    return [{"id": t.id, "content": t.content, "due": str(t.due_date)} for t in tasks]


@tool
async def task_complete(user_id: int, task_id: str) -> dict:
    """Mark task as completed."""
    from src.services.firebase.pkm import update_smart_task

    await update_smart_task(user_id, task_id, status="completed")
    return {"id": task_id, "status": "completed"}
```

### Phase D: Agent Integration (4h)

#### D.1. Telegram Chat Agent (2h)

Update `api/routes/telegram.py`:
```python
"""Telegram webhook with SDK agent."""

from src.sdk import create_agent, run_agent
from src.core.state import StateManager
from src.core.trace import TraceContext
from src.core.resilience import get_circuit_manager
import structlog

logger = structlog.get_logger()


async def handle_telegram_message(user_id: int, message: str, tier: str):
    """Handle Telegram message with SDK agent."""

    # Initialize tracing
    trace = TraceContext(user_id=user_id, source="telegram")

    # Create SDK agent with all hooks
    agent = create_agent(
        user_id=user_id,
        tier=tier,
        circuit_manager=get_circuit_manager(),
    )

    # Load user context (tasks, preferences)
    state = StateManager()
    context = await state.get_user_context(user_id)

    try:
        response = await run_agent(agent, message, context)
        trace.complete(success=True)
        return response
    except Exception as e:
        trace.complete(success=False, error=str(e))
        logger.error("telegram_agent_failed", error=str(e), user_id=user_id)
        raise
```

#### D.2. GitHub Agent (1h)

Update `src/agents/github.py`:
```python
"""GitHub agent using SDK."""

from src.sdk import create_agent, run_agent
from src.sdk.config import AgentConfig
import structlog

logger = structlog.get_logger()


async def run_github_agent(event_type: str, payload: dict):
    """Run GitHub agent for webhook events."""

    # GitHub agent uses admin tier (no limits)
    agent = create_agent(
        user_id=0,  # System user
        tier="admin",
        config=AgentConfig(model="claude-sonnet-4-20250514"),
    )

    prompt = f"GitHub {event_type} event:\n{payload}"

    return await run_agent(agent, prompt)
```

#### D.3. Content Agent (1h)

Update `src/agents/content.py`:
```python
"""Content agent using SDK."""

from src.sdk import create_agent, run_agent
import structlog

logger = structlog.get_logger()


async def run_content_agent(user_id: int, skill_name: str, params: dict):
    """Run content agent for skill execution."""

    # Content agent gets user's tier
    from src.services.firebase.users import get_user_tier
    tier = await get_user_tier(user_id)

    agent = create_agent(user_id=user_id, tier=tier)

    prompt = f"Execute skill '{skill_name}' with params: {params}"

    return await run_agent(agent, prompt)
```

### Phase E: Cleanup (2h)

#### E.1. Delete Deprecated Files (0.5h)

```bash
# Delete old implementations
rm agents/src/services/agentic.py
rm agents/src/services/llm.py
rm -rf agents/src/tools/  # Moved to src/sdk/tools/
```

#### E.2. Update Imports (1h)

Update all files importing from deleted modules:
- `main.py` → Use `src.sdk`
- `api/routes/*.py` → Use `src.sdk`
- `src/agents/*.py` → Use `src.sdk`

#### E.3. Final Testing (0.5h)

```bash
# Run full test suite
python3 -m pytest agents/tests/ -v

# Deploy to staging
modal deploy agents/main.py --env=staging

# Smoke test all endpoints
curl -X POST .../webhook/telegram -d '{"message":"test"}'
```

## Todo List

### Phase A: SDK Foundation
- [ ] Create `src/sdk/` package structure with hooks/ and tools/ subdirs
- [ ] Add claude-agents-sdk to requirements.txt
- [ ] Implement `agent.py` with create_agent/run_agent
- [ ] Implement `config.py` with TierLimits and AgentConfig

### Phase B: Hooks Migration
- [ ] Implement CircuitBreakerHook (PreToolUse)
- [ ] Implement TrustRulesHook (PreToolUse + PostToolUse)
- [ ] Implement TracingHook (PostToolUse)
- [ ] Implement ImprovementHook (PostToolUse)
- [ ] Create hooks/__init__.py with get_all_hooks()

### Phase C: Tools Migration
- [ ] Migrate web_search tool (Exa + Tavily fallback)
- [ ] Migrate search_memory tool (Qdrant)
- [ ] Migrate run_python tool (code execution)
- [ ] Migrate get_datetime tool
- [ ] Migrate gemini_* tools (vision, grounding, thinking)
- [ ] Create task_* tools (CRUD for SmartTask)
- [ ] Create calendar_* tool stubs (Phase 3)
- [ ] Create tools/__init__.py with get_all_tools()

### Phase D: Agent Integration
- [ ] Update Telegram chat handler to use SDK agent
- [ ] Update GitHub agent to use SDK agent
- [ ] Update Content agent to use SDK agent
- [ ] Verify all existing flows work with SDK

### Phase E: Cleanup
- [ ] Delete src/services/agentic.py
- [ ] Delete src/services/llm.py
- [ ] Delete src/tools/ directory
- [ ] Update all imports throughout codebase
- [ ] Run full test suite
- [ ] Deploy to staging and validate

## Success Criteria

1. SDK agent handles all Telegram chat interactions
2. All 7 existing tools migrated to @tool decorator pattern
3. All 4 hooks (circuit, trust, trace, improve) functional
4. Telegram, GitHub, Content agents all using SDK
5. Circuit breakers integrate via PreToolUse hooks
6. Tracing preserved via PostToolUse hooks
7. Self-improvement triggers on errors via hooks
8. No increase in response latency (within 10%)
9. agentic.py and llm.py deleted, no fallback needed
10. All existing tests pass after migration

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| SDK API changes | Medium | Low | Pin SDK version |
| Modal incompatibility | High | Low | Test thoroughly in dev |
| Performance regression | Medium | Medium | Benchmark before/after |
| Trust rule gaps | High | Medium | Comprehensive test cases |

## Security Considerations

1. SDK client uses existing Modal secrets
2. Trust rules enforce user-level permissions
3. Tool inputs validated before execution
4. No direct LLM access to Firebase credentials
5. Audit logging for all trust rule decisions

## Next Steps

After Phase 0 complete:
1. Proceed to [Phase 1: Core Foundation](phase-01-core-foundation.md) (SmartTask, NLP)
2. All subsequent phases use SDK agent (no more agentic.py)
3. Monitor SDK performance in production
4. Collect baseline metrics for comparison

## Unresolved Questions

1. SDK version pinning strategy? → Use `>=0.5.0,<1.0.0`
2. How to handle SDK rate limits vs existing circuit breakers? → Circuit hooks block before SDK call
3. Should scheduled jobs (daily_summary, cleanup) use SDK or stay simple? → Stay simple, not agentic
4. Separate PR or monolithic change? → Monolithic per big bang decision
