# Code Standards

## Python Requirements

- **Version:** Python 3.11+
- **Type Hints:** Required for all functions
- **Docstrings:** Google style for public APIs
- **Logging:** Use `structlog` for structured logging

## Project Structure

```
agents/
├── modal.toml                    # Modal project config
├── requirements.txt              # Python dependencies
├── main.py                       # Modal app entry point
├── src/
│   ├── __init__.py
│   ├── config.py                 # Environment configuration
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py               # BaseAgent class
│   │   ├── content_generator.py  # Content Agent
│   │   ├── data_processor.py     # Data Agent
│   │   └── github_automation.py  # GitHub Agent
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agentic.py            # Agentic loop with tools
│   │   ├── llm.py                # Claude API wrapper
│   │   ├── firebase.py           # Firebase client
│   │   ├── qdrant.py             # Qdrant client
│   │   ├── embeddings.py         # Embedding generation
│   │   └── token_refresh.py      # Token utilities
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py               # Base tool interface
│   │   ├── registry.py           # Tool registry
│   │   ├── web_search.py         # Exa + Tavily search
│   │   ├── web_reader.py         # URL content fetching
│   │   ├── code_exec.py          # Python execution
│   │   ├── datetime_tool.py      # Date/time utilities
│   │   └── memory_search.py      # Qdrant search
│   ├── core/
│   │   ├── __init__.py
│   │   ├── state.py             # L1/L2 state management
│   │   ├── resilience.py        # Circuit breakers, retry logic
│   │   ├── trace.py             # Execution tracing
│   │   ├── improvement.py       # Self-improvement service
│   │   ├── router.py            # Semantic skill routing
│   │   ├── orchestrator.py      # Multi-skill orchestration
│   │   ├── chain.py             # Skill chaining
│   │   ├── evaluator.py         # Quality evaluation
│   │   └── context_optimization.py
│   ├── skills/
│   │   └── registry.py           # Progressive disclosure
│   └── utils/
│       ├── __init__.py
│       └── logging.py            # Structured logging
├── skills/                       # Skill info.md files (II Framework)
│   ├── CLAUDE.md
│   ├── telegram-chat/info.md
│   ├── github/info.md
│   └── ...
└── tests/
```

## II Framework Conventions

### Skill Structure

Each skill follows Information + Implementation pattern:

```
skills/
├── telegram-chat/
│   └── info.md              # Information: instructions, memory, plans
├── github/
│   └── info.md
├── planning/
│   └── info.md
└── pdf/
    ├── info.md
    └── scripts/             # Optional: utility scripts
        ├── extract_form_field_info.py
        └── fill_pdf_form_with_annotations.py
```

### info.md Template

```markdown
---
name: skill-name
description: Brief description for routing
category: development|design|media|document
deployment: local|remote|both
---

# [Skill Name] Agent

## Instructions
[What this agent does and how]

## Tools Available
[List of functions the agent can call]

## Memory
[Accumulated learnings from past runs]

## Error History
[Past errors and how they were resolved]

## Current Plan
[Active goals and next steps]
```

### Progressive Disclosure Pattern

Layer 1 - Summary (fast discovery):
```python
@dataclass
class SkillSummary:
    name: str
    description: str
    category: Optional[str] = None
    path: Optional[Path] = None
```

Layer 2 - Full content (on activation):
```python
@dataclass
class Skill:
    name: str
    description: str
    body: str
    frontmatter: Dict[str, Any]
    memory: str = ""
    error_history: str = ""
```

## Tool Development

### Tool Interface

```python
from src.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Description for LLM"

    def get_definition(self) -> dict:
        """Return Anthropic-compatible tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "..."},
                },
                "required": ["param1"]
            }
        }

    async def execute(self, **kwargs) -> str:
        """Execute tool and return result string."""
        param1 = kwargs.get("param1")
        # ... implementation
        return "Result"
```

### Tool Registration

```python
from src.tools import get_registry, init_default_tools

# Initialize all default tools
init_default_tools()

# Get registry for tool definitions
registry = get_registry()
tools = registry.get_definitions()  # For LLM API call

# Execute a tool
result = await registry.execute("web_search", {"query": "..."})
```

## Circuit Breaker Pattern

```python
from src.core.resilience import CircuitBreaker, with_retry

# Pre-configured circuits
from src.core import (
    exa_circuit, tavily_circuit, firebase_circuit,
    qdrant_circuit, claude_circuit, telegram_circuit
)

# Use circuit breaker
async def call_external_api():
    if not exa_circuit.can_execute():
        return "Service unavailable (circuit open)"
    try:
        result = await exa_api_call()
        exa_circuit.record_success()
        return result
    except Exception as e:
        exa_circuit.record_failure()
        raise

# Use retry decorator
@with_retry(max_attempts=3, base_delay=1.0)
async def reliable_operation():
    ...
```

## Execution Tracing

```python
from src.core.trace import TraceContext

async with TraceContext(user_id="123", skill="planning") as trace:
    # All tool calls within this context are traced
    result = await registry.execute("web_search", {"query": "..."})
    # trace.tool_traces contains timing/error info

# Save trace to Firebase
await trace.save()
```

## Agentic Loop Pattern

```python
async def run_agentic_loop(
    user_message: str,
    system: Optional[str] = None,
    context: Optional[List[Dict]] = None,
) -> str:
    """Run agentic loop with tool execution.

    - Max 5 iterations to prevent runaway
    - Handles tool_use stop_reason
    - Returns accumulated text response
    """
    # Initialize tools
    init_default_tools()
    registry = get_registry()
    tools = registry.get_definitions()

    # Build messages
    messages = [{"role": "user", "content": user_message}]

    while iterations < MAX_ITERATIONS:
        response = llm.chat(messages=messages, tools=tools)

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            # Execute tools and append results
            for block in response.content:
                if block.type == "tool_use":
                    result = await registry.execute(block.name, block.input)
                    # Append tool result as user message
```

## Modal.com Patterns

### Function Decorators

```python
# Always-on for low latency (Telegram chat)
@app.function(min_containers=1)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def telegram_chat_agent():
    return create_web_app()

# Scheduled execution (GitHub monitor)
@app.function(schedule=modal.Cron("0 * * * *"))
async def github_monitor():
    ...

# On-demand function
@app.function(timeout=120)
async def content_agent(task: dict):
    ...
```

### Secrets Management

```bash
# Create secrets
modal secret create anthropic-credentials ANTHROPIC_API_KEY=sk-ant-...
modal secret create telegram-credentials TELEGRAM_BOT_TOKEN=...
modal secret create firebase-credentials FIREBASE_PROJECT_ID=... FIREBASE_CREDENTIALS_JSON=...
modal secret create qdrant-credentials QDRANT_URL=... QDRANT_API_KEY=...
modal secret create exa-credentials EXA_API_KEY=...
modal secret create tavily-credentials TAVILY_API_KEY=...
modal secret create github-credentials GITHUB_TOKEN=...
```

### Volume Usage

```python
skills_volume = modal.Volume.from_name("skills-volume", create_if_missing=True)

@app.function(volumes={"/skills": skills_volume})
def my_function():
    # Read skill info
    info = Path("/skills/telegram-chat/info.md").read_text()

    # Write updated memory
    Path("/skills/telegram-chat/info.md").write_text(updated_info)
    skills_volume.commit()  # Persist changes
```

## Dependencies

```
modal>=0.60.0
fastapi>=0.109.0
uvicorn>=0.27.0
anthropic>=0.40.0
firebase-admin>=6.4.0
qdrant-client>=1.7.0
python-telegram-bot>=21.0
PyGithub>=2.1.0
httpx>=0.26.0
pydantic>=2.5.0
pydantic-settings>=2.0.0
structlog>=24.1.0
exa-py>=1.0.0
tavily-python>=0.3.0
numpy>=1.24.0
PyYAML>=6.0.0

# Document Processing
python-docx>=1.1.0
docxtpl>=0.16.0
docx2python>=3.0.0
openpyxl>=3.1.0
formulas>=1.2.0
python-pptx>=0.6.23
pypdf>=4.0.0
pdfplumber>=0.10.0
```

## Logging

Use `structlog` for structured logging:

```python
from src.utils.logging import get_logger

logger = get_logger()

# Component binding
logger = logger.bind(component="SkillRouter")

# Structured logging
logger.info("task_completed", agent="telegram", user_id="123")
logger.error("api_error", error=str(e), context="webhook")
logger.warning("skill_not_found", name=skill_name)
```

## Testing Strategy

1. **Unit Tests** - Service layer functions
2. **Integration Tests** - Agent workflows with mocked APIs
3. **Test Functions** - Modal test_* functions for service verification

```python
# Test functions in main.py
@app.function(...)
def test_firebase():
    """Test Firebase connection."""
    ...

@app.function(...)
def test_llm():
    """Test LLM providers."""
    ...
```

## Security

- Never commit secrets to git
- Use Modal Secrets for all credentials
- Verify webhook signatures (Telegram, GitHub)
- Firebase credentials as JSON secret
- Rotate tokens periodically
- Sanitize user input before code execution
