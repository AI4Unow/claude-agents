# Code Standards

## Python Requirements

- **Version:** Python 3.11+
- **Type Hints:** Required for all functions
- **Docstrings:** Google style for public APIs

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
│   │   ├── zalo_chat.py          # Zalo Chat Agent
│   │   ├── github_automation.py  # GitHub Agent
│   │   ├── data_processor.py     # Data Agent
│   │   └── content_generator.py  # Content Agent
│   ├── services/
│   │   ├── __init__.py
│   │   ├── firebase.py           # Firebase client
│   │   ├── qdrant.py             # Qdrant client
│   │   ├── anthropic.py          # Claude API wrapper
│   │   └── embeddings.py         # Embedding generation
│   └── utils/
│       ├── __init__.py
│       └── logging.py            # Structured logging
├── skills/                       # Hot-reload skills (II Framework)
│   ├── CLAUDE.md
│   └── ...
└── tests/
    └── ...
```

## II Framework Conventions

### Skill Structure

Each skill follows Information + Implementation pattern:

```
skills/
├── zalo-chat/
│   ├── info.md              # Information: instructions, memory, plans
│   └── agent.py             # Implementation: execution code
├── github-automation/
│   ├── info.md
│   └── agent.py
└── ...
```

### info.md Template

```markdown
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

### agent.py Template

```python
import modal
from pathlib import Path

app = modal.App("skill-name")
volume = modal.Volume.from_name("skills-volume")

@app.function(
    volumes={"/skills": volume},
    secrets=[modal.Secret.from_name("api-keys")],
    schedule=modal.Cron("0 9 * * *"),
    timeout=3600,
)
async def run():
    # 1. Read information
    info = Path("/skills/skill-name/info.md").read_text()

    # 2. Execute with LLM
    result = await execute_with_llm(info, task)

    # 3. Self-improve if needed
    if result.needs_improvement:
        improved_info = await improve_instructions(info, result.error)
        Path("/skills/skill-name/info.md").write_text(improved_info)
        volume.commit()

    return result
```

## Modal.com Patterns

### Function Decorators

```python
# Always-on for low latency
@app.function(min_containers=1)

# Scheduled execution
@app.function(schedule=modal.Cron("0 * * * *"))

# Web endpoint
@modal.asgi_app()
```

### Secrets Management

```bash
modal secret create anthropic-api-key ANTHROPIC_API_KEY=sk-ant-...
modal secret create firebase-credentials FIREBASE_PROJECT_ID=...
```

### Volume Usage

```python
volume = modal.Volume.from_name("skills-volume", create_if_missing=True)

@app.function(volumes={"/skills": volume})
def my_function():
    # Read/write to /skills/
    volume.commit()  # Persist changes
```

## Dependencies

```
modal>=0.60.0
fastapi>=0.109.0
uvicorn>=0.27.0
anthropic>=0.18.0
firebase-admin>=6.4.0
qdrant-client>=1.7.0
google-cloud-aiplatform>=1.40.0
PyGithub>=2.1.0
httpx>=0.26.0
pydantic>=2.5.0
structlog>=24.1.0
```

## Logging

Use `structlog` for structured logging:

```python
import structlog
logger = structlog.get_logger()

logger.info("task_completed", agent="zalo", user_id="123")
logger.error("api_error", error=str(e), context="webhook")
```

## Testing Strategy

1. **Unit Tests** - Service layer functions
2. **Integration Tests** - Agent workflows with mocked APIs
3. **E2E Tests** - Full flow with test Zalo account

## Security

- Never commit secrets to git
- Use Modal Secrets for all credentials
- Verify webhook signatures (Zalo, GitHub)
- Firebase credentials as JSON secret
- Rotate tokens periodically
