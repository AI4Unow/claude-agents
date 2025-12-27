# Phase 1: Project Setup & Modal Configuration

## Context

- Plan: [plan.md](./plan.md)
- Brainstorm: [brainstorm report](../reports/brainstorm-251226-1500-modal-claude-agents-architecture.md)

## Overview

**Priority:** P1 - Foundation
**Status:** Pending
**Effort:** 3h

Setup Modal.com project, configure secrets, create base infrastructure for agent deployment.

## Requirements

### Functional
- Modal CLI installed and authenticated
- Project structure with modular agent organization
- Secrets configured for all external services
- Skills volume created and mountable
- Base agent class for shared functionality

### Non-Functional
- Python 3.11+ runtime
- Reproducible builds via modal.toml
- Environment isolation between dev/prod

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
│   │   ├── telegram_chat.py      # Telegram Chat Agent
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
├── skills/                       # Claude Code skills (hot-reload)
│   ├── CLAUDE.md
│   └── ...
└── tests/
    └── ...
```

## Implementation Steps

### 1. Install Modal CLI

```bash
pip install modal
modal setup  # Browser auth flow
```

### 2. Create modal.toml

```toml
[project]
name = "claude-agents"

[settings]
default_workspace = "default"
```

### 3. Create requirements.txt

```
modal>=0.60.0
fastapi>=0.109.0
uvicorn>=0.27.0
anthropic>=0.18.0
firebase-admin>=6.4.0
qdrant-client>=1.7.0
google-cloud-aiplatform>=1.40.0
python-telegram-bot>=21.0
PyGithub>=2.1.0
httpx>=0.26.0
pydantic>=2.5.0
structlog>=24.1.0
```

### 4. Create main.py (Modal App Entry)

```python
import modal

# Define the Modal app
app = modal.App("claude-agents")

# Define container image (no CLI needed - II Framework uses LLM API directly)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl")
    .pip_install_from_requirements("requirements.txt")
)

# Skills volume - stores mutable info.md files (II Framework: Information layer)
skills_volume = modal.Volume.from_name("skills-volume", create_if_missing=True)

# Define secrets
secrets = [
    modal.Secret.from_name("anthropic-api-key"),
    modal.Secret.from_name("firebase-credentials"),
    modal.Secret.from_name("gcp-credentials"),
    modal.Secret.from_name("telegram-credentials"),
    modal.Secret.from_name("github-token"),
    modal.Secret.from_name("qdrant-credentials"),
]
```

### 5. Create src/config.py

```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    # Firebase
    firebase_project_id: str = ""

    # Telegram
    telegram_bot_token: str = ""

    # GitHub
    github_token: str = ""

    # GCP (for Vertex AI)
    gcp_project_id: str = ""
    gcp_location: str = "us-central1"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    class Config:
        env_file = ".env"

settings = Settings()
```

### 6. Create src/agents/base.py (II Framework)

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
import json
import os
import structlog
import anthropic

logger = structlog.get_logger()

class BaseAgent(ABC):
    """
    Base class for all agents using II Framework.

    II Framework = Information (.md) + Implementation (.py)
    - info.md: Mutable instructions stored in Modal Volume
    - agent.py: Immutable code deployed to Modal Server
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.logger = logger.bind(agent_id=agent_id)
        self.skills_path = Path("/skills")
        self.info_path = self.skills_path / agent_id / "info.md"
        self.client = anthropic.Anthropic()

    @abstractmethod
    async def process(self, task: dict) -> dict:
        """Process a task and return result."""
        pass

    def read_instructions(self) -> str:
        """Read current instructions from info.md (Information layer)."""
        if self.info_path.exists():
            return self.info_path.read_text()
        return ""

    def write_instructions(self, content: str) -> None:
        """Write updated instructions to info.md (Self-improvement)."""
        self.info_path.parent.mkdir(parents=True, exist_ok=True)
        self.info_path.write_text(content)
        # Note: Must call volume.commit() after this in Modal function

    async def execute_with_llm(
        self,
        user_message: str,
        context: List[Dict] = None,
        model: str = "claude-sonnet-4-20250514"
    ) -> str:
        """
        Execute task using LLM with info.md as system instructions.

        Args:
            user_message: User's request
            context: Previous conversation context
            model: LLM model to use

        Returns:
            LLM response text
        """
        # Read current instructions (self-improving, may have changed)
        instructions = self.read_instructions()

        # Build messages with context
        messages = []
        if context:
            for c in context[-5:]:  # Last 5 messages
                messages.append({
                    "role": c.get("role", "user"),
                    "content": c.get("content", "")
                })

        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=2048,
                system=instructions,
                messages=messages
            )
            return response.content[0].text

        except Exception as e:
            self.logger.error("llm_error", error=str(e))
            raise

    async def self_improve(self, error: str, context: str = "") -> str:
        """
        Self-improvement loop: LLM analyzes error and rewrites info.md.

        Args:
            error: Error message or issue description
            context: Additional context about what went wrong

        Returns:
            Improved instructions
        """
        current_instructions = self.read_instructions()

        improvement_prompt = f"""You are improving your own instructions based on an error.

CURRENT INSTRUCTIONS:
{current_instructions}

ERROR ENCOUNTERED:
{error}

CONTEXT:
{context}

Analyze what went wrong and rewrite the instructions to prevent this error.
Return the complete updated instructions in markdown format.
Add this fix to the "## Error History" section with today's date.
Update "## Memory" section with what you learned."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": improvement_prompt}]
        )

        improved = response.content[0].text
        self.write_instructions(improved)

        self.logger.info("self_improved",
            agent=self.agent_id,
            error_summary=error[:100]
        )

        return improved

    async def forward_to_user(
        self,
        user_id: str,
        message: str,
        bypass_supervisor: bool = True
    ) -> bool:
        """Forward response directly to user (prevents telephone game)."""
        if bypass_supervisor:
            from src.agents.telegram_chat import TelegramChatAgent
            telegram = TelegramChatAgent()
            return await telegram.send_message(user_id, message)
        else:
            return {"for_supervisor": message}

    async def log_activity(self, action: str, details: dict, level: str = "info"):
        """Log agent activity to Firebase."""
        from src.services.firebase import log_activity
        await log_activity(
            agent=self.agent_id,
            action=action,
            details=details,
            level=level
        )

    async def update_status(self, status: str):
        """Update agent status in Firebase."""
        from src.services.firebase import update_agent_status
        await update_agent_status(self.agent_id, status)
```

### 7. Configure Modal Secrets

```bash
# Anthropic API Key
modal secret create anthropic-api-key ANTHROPIC_API_KEY=sk-ant-...

# Firebase (JSON credentials)
modal secret create firebase-credentials \
  FIREBASE_PROJECT_ID=your-project-id \
  FIREBASE_CREDENTIALS='{"type":"service_account",...}'

# Telegram (get token from @BotFather)
modal secret create telegram-credentials \
  TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# GitHub
modal secret create github-token GITHUB_TOKEN=ghp_...

# GCP (for Vertex AI embeddings)
# Option 1: Service account JSON
modal secret create gcp-credentials \
  GCP_PROJECT_ID=your-project-id \
  GCP_LOCATION=us-central1 \
  GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'

# Option 2: If Modal is running on GCP, use default credentials
# Just set GCP_PROJECT_ID and GCP_LOCATION
```

### 8. GitHub-to-Volume Skills Sync

Skills are stored in GitHub for version control, then synced to Modal Volume.

#### Add to main.py

```python
import subprocess
import os

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("github-token")],
    volumes={"/skills": skills_volume},
    timeout=120,
)
def sync_skills_from_github():
    """
    Sync skills from GitHub repo to Modal Volume.

    Triggered by:
    - Scheduled cron (hourly)
    - GitHub webhook (on push)
    - Manual invocation
    """
    repo_url = os.environ.get("SKILLS_REPO", "owner/claude-agents")
    branch = os.environ.get("SKILLS_BRANCH", "main")
    skills_path = os.environ.get("SKILLS_PATH", "skills")  # Path within repo

    token = os.environ["GITHUB_TOKEN"]

    # Clone or pull the repo
    repo_dir = "/tmp/repo"

    if os.path.exists(repo_dir):
        # Pull latest changes
        subprocess.run(
            ["git", "-C", repo_dir, "pull", "origin", branch],
            check=True
        )
    else:
        # Clone the repo
        clone_url = f"https://{token}@github.com/{repo_url}.git"
        subprocess.run(
            ["git", "clone", "--depth", "1", "-b", branch, clone_url, repo_dir],
            check=True
        )

    # Copy skills to volume
    src_skills = os.path.join(repo_dir, skills_path)
    subprocess.run(
        ["cp", "-r", f"{src_skills}/.", "/skills/"],
        check=True
    )

    # Commit volume changes
    skills_volume.commit()

    return {"status": "synced", "repo": repo_url, "branch": branch}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("github-token")],
    volumes={"/skills": skills_volume},
    schedule=modal.Cron("0 * * * *"),  # Hourly sync
    timeout=120,
)
def scheduled_skills_sync():
    """Hourly skills sync from GitHub."""
    return sync_skills_from_github.local()


# Webhook endpoint for GitHub push events
@web_app.post("/webhook/github-skills")
async def github_skills_webhook(request: Request):
    """
    GitHub webhook to trigger skills sync on push.

    Configure in GitHub repo:
    - Webhook URL: https://<modal-app>.modal.run/webhook/github-skills
    - Events: Push
    - Secret: Use GITHUB_WEBHOOK_SECRET
    """
    import hmac
    import hashlib

    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Verify webhook signature
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Only sync on push to main branch
    ref = payload.get("ref", "")
    if ref == "refs/heads/main":
        sync_skills_from_github.spawn()  # Async trigger
        return {"status": "sync_triggered"}

    return {"status": "ignored", "ref": ref}
```

#### Configure Skills Repo Secret

```bash
# Add skills repo config to github-token secret
modal secret create github-token \
  GITHUB_TOKEN=ghp_... \
  SKILLS_REPO=owner/claude-agents \
  SKILLS_BRANCH=main \
  SKILLS_PATH=skills \
  GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

#### GitHub Repo Structure

```
owner/claude-agents/
├── skills/                    # Synced to Modal Volume
│   ├── CLAUDE.md
│   ├── github-skills/
│   │   └── ...
│   └── data-skills/
│       └── ...
├── src/                       # Agent code (deployed via modal deploy)
│   └── ...
└── main.py
```

### 9. Test Deployment

```bash
# Deploy to Modal
modal deploy main.py

# Check logs
modal app logs claude-agents
```

## Files to Create

| Path | Action | Description |
|------|--------|-------------|
| `agents/modal.toml` | Create | Modal project config |
| `agents/requirements.txt` | Create | Python dependencies |
| `agents/main.py` | Create | Modal app entry |
| `agents/src/__init__.py` | Create | Package init |
| `agents/src/config.py` | Create | Settings management |
| `agents/src/agents/__init__.py` | Create | Agents package |
| `agents/src/agents/base.py` | Create | BaseAgent class |
| `agents/src/services/__init__.py` | Create | Services package |
| `agents/src/utils/__init__.py` | Create | Utils package |
| `agents/src/utils/logging.py` | Create | Logging config |
| `agents/skills/CLAUDE.md` | Create | Skills config |

## Todo List

- [ ] Install Modal CLI locally
- [ ] Run `modal setup` for auth
- [ ] Create GitHub repo with project structure
- [ ] Create modal.toml
- [ ] Create requirements.txt
- [ ] Create main.py with app definition
- [ ] Create config.py with Settings
- [ ] Create base.py with BaseAgent
- [ ] Configure all Modal secrets (including SKILLS_REPO config)
- [ ] Create skills volume
- [ ] Add sync_skills_from_github function
- [ ] Configure GitHub webhook for skills sync
- [ ] Test `modal deploy`
- [ ] Verify skills sync works

## Success Criteria

- [ ] `modal deploy` succeeds without errors
- [ ] All secrets accessible in container
- [ ] Skills volume mounts correctly
- [ ] GitHub-to-Volume sync works (manual + webhook)
- [ ] Base project structure in place

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Modal auth issues | Blocking | Use `modal token new` for CI/CD |
| Secret misconfiguration | Auth failures | Test each secret individually |
| Python version mismatch | Runtime errors | Pin Python 3.11 in image |

## Security Considerations

- Never commit secrets to git
- Use Modal Secrets, not env files in container
- Firebase credentials as JSON secret
- Rotate tokens periodically

## Next Steps

After completing this phase:
1. Proceed to Phase 2: Firebase Integration
2. Verify secrets work in deployed container
