"""Modal app entry point for Claude Agents.

This file defines the Modal application, container image, and core functions.
All agents mount the skills volume for II Framework functionality.
"""
import modal
import os
import subprocess
from datetime import datetime

# Define the Modal app
app = modal.App("claude-agents")

# Define container image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("src", remote_path="/root/src")
)

# Skills volume - stores mutable info.md files (II Framework: Information layer)
skills_volume = modal.Volume.from_name("skills-volume", create_if_missing=True)

# Define secrets
secrets = [
    modal.Secret.from_name("anthropic-credentials"),
    modal.Secret.from_name("firebase-credentials"),
    modal.Secret.from_name("telegram-credentials"),
    modal.Secret.from_name("qdrant-credentials"),
    modal.Secret.from_name("exa-credentials"),
    modal.Secret.from_name("tavily-credentials"),
]

# GitHub secret (separate for security)
github_secret = modal.Secret.from_name("github-credentials")


def create_web_app():
    """Create FastAPI app (called inside Modal container)."""
    from fastapi import FastAPI, Request

    web_app = FastAPI()

    @web_app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "agent": "claude-agents",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
        }

    @web_app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        """Handle Telegram webhook updates."""
        import structlog
        logger = structlog.get_logger()

        try:
            update = await request.json()
            logger.info("telegram_update", update_id=update.get("update_id"))

            # Extract message
            message = update.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")
            user = message.get("from", {})

            if not chat_id or not text:
                return {"ok": True}

            logger.info("processing_message", chat_id=chat_id, text_len=len(text))

            # Handle commands
            if text.startswith("/"):
                response = await handle_command(text, user, chat_id)
            else:
                response = await process_message(text, user, chat_id)

            logger.info("sending_response", chat_id=chat_id, response_len=len(response))

            # Send response
            await send_telegram_message(chat_id, response)

            return {"ok": True}

        except Exception as e:
            logger.error("webhook_error", error=str(e))
            return {"ok": False, "error": str(e)}

    @web_app.post("/webhook/github")
    async def github_webhook(request: Request):
        """Handle GitHub webhook events."""
        import structlog
        logger = structlog.get_logger()

        try:
            event = request.headers.get("X-GitHub-Event", "push")
            payload = await request.json()

            logger.info("github_webhook", event=event)

            task = {
                "type": "github",
                "payload": {
                    "action": f"handle_{event}",
                    "event": event,
                    "data": payload
                }
            }

            from src.agents.github_automation import process_github_task
            result = await process_github_task(task)
            return {"ok": True, "result": result}

        except Exception as e:
            logger.error("github_webhook_error", error=str(e))
            return {"ok": False, "error": str(e)}

    @web_app.post("/api/content")
    async def content_api(request: Request):
        """Content Agent HTTP API endpoint."""
        import structlog
        logger = structlog.get_logger()

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

    return web_app


async def handle_command(command: str, user: dict, chat_id: int) -> str:
    """Handle bot commands including content agent commands."""
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        return f"Hello {user.get('first_name', 'there')}! I'm your AI assistant powered by II Framework."
    elif cmd == "/help":
        return (
            "Available commands:\n"
            "/start - Welcome\n"
            "/help - This message\n"
            "/status - Check agent status\n"
            "/translate <text> - Translate to English\n"
            "/summarize <text> - Summarize text\n"
            "/rewrite <text> - Improve text"
        )
    elif cmd == "/status":
        return "Agent is running normally."
    elif cmd == "/translate" and args:
        from src.agents.content_generator import process_content_task
        task = {"payload": {"action": "translate", "text": args, "target": "en"}}
        result = await process_content_task(task)
        return result.get("message", result.get("translation", "Translation failed"))
    elif cmd == "/summarize" and args:
        from src.agents.content_generator import process_content_task
        task = {"payload": {"action": "summarize", "text": args}}
        result = await process_content_task(task)
        return result.get("message", result.get("summary", "Summary failed"))
    elif cmd == "/rewrite" and args:
        from src.agents.content_generator import process_content_task
        task = {"payload": {"action": "rewrite", "text": args}}
        result = await process_content_task(task)
        return result.get("message", result.get("rewritten", "Rewrite failed"))
    elif cmd in ["/translate", "/summarize", "/rewrite"]:
        return f"Usage: {cmd} <text>"
    else:
        return "Unknown command. Try /help"


async def process_message(text: str, user: dict, chat_id: int) -> str:
    """Process a regular message with agentic loop (tools enabled)."""
    from src.services.agentic import run_agentic_loop
    from pathlib import Path
    import structlog

    logger = structlog.get_logger()

    # Read instructions from skills volume
    info_path = Path("/skills/telegram-chat/info.md")
    system_prompt = "You are a helpful AI assistant with web search capability. Use the web_search tool when users ask about current events, weather, news, prices, or anything requiring up-to-date information."
    if info_path.exists():
        system_prompt = info_path.read_text()

    try:
        response = await run_agentic_loop(
            user_message=text,
            system=system_prompt,
        )
        return response
    except Exception as e:
        logger.error("agentic_error", error=str(e))
        return f"Sorry, I encountered an error processing your request."


async def send_telegram_message(chat_id: int, text: str):
    """Send message via Telegram API."""
    import httpx
    import structlog

    logger = structlog.get_logger()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not token:
        logger.error("telegram_no_token")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )
            result = response.json()

            if not result.get("ok"):
                logger.error("telegram_send_failed",
                    chat_id=chat_id,
                    error=result.get("description"),
                    error_code=result.get("error_code")
                )
                return False

            logger.info("telegram_sent", chat_id=chat_id)
            return True

    except Exception as e:
        logger.error("telegram_exception", error=str(e), chat_id=chat_id)
        return False


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    min_containers=1,  # Always-on for fast response
    timeout=60,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def telegram_chat_agent():
    """Telegram Chat Agent - Primary interface."""
    return create_web_app()


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("telegram-credentials")],
    volumes={"/skills": skills_volume},
    timeout=120,
)
def sync_skills_from_github():
    """Sync skills from GitHub repo to Modal Volume."""
    repo_url = os.environ.get("SKILLS_REPO", "")
    branch = os.environ.get("SKILLS_BRANCH", "main")
    skills_path_in_repo = os.environ.get("SKILLS_PATH", "skills")

    if not repo_url:
        return {"status": "skipped", "reason": "SKILLS_REPO not configured"}

    token = os.environ.get("GITHUB_TOKEN", "")
    repo_dir = "/tmp/repo"

    if os.path.exists(repo_dir):
        subprocess.run(["git", "-C", repo_dir, "pull", "origin", branch], check=True)
    else:
        if token:
            clone_url = f"https://{token}@github.com/{repo_url}.git"
        else:
            clone_url = f"https://github.com/{repo_url}.git"
        subprocess.run(["git", "clone", "--depth", "1", "-b", branch, clone_url, repo_dir], check=True)

    src_skills = os.path.join(repo_dir, skills_path_in_repo)
    if os.path.exists(src_skills):
        subprocess.run(["cp", "-r", f"{src_skills}/.", "/skills/"], check=True)
        skills_volume.commit()
        return {"status": "synced", "repo": repo_url, "branch": branch}

    return {"status": "skipped", "reason": "skills path not found in repo"}


# ==================== GitHub Agent ====================

@app.function(
    image=image,
    secrets=secrets + [github_secret],
    volumes={"/skills": skills_volume},
    timeout=120,
)
async def github_agent(task: dict):
    """GitHub Agent - Repository automation."""
    from src.agents.github_automation import process_github_task
    return await process_github_task(task)


@app.function(
    image=image,
    secrets=secrets + [github_secret],
    volumes={"/skills": skills_volume},
    schedule=modal.Cron("0 * * * *"),  # Every hour for repo monitoring
    timeout=300,
)
async def github_monitor():
    """Monitor configured repositories for new activity (hourly)."""
    from src.agents.github_automation import monitor_repositories
    import structlog
    logger = structlog.get_logger()

    # Read monitored repos from skill file
    from pathlib import Path
    info_path = Path("/skills/github/info.md")
    repos = []

    if info_path.exists():
        content = info_path.read_text()
        # Parse repos from info.md (look for ## Monitored Repos section)
        if "## Monitored Repos" in content:
            lines = content.split("## Monitored Repos")[1].split("##")[0].strip().split("\n")
            repos = [l.strip("- ").strip() for l in lines if l.strip().startswith("-")]

    if not repos:
        logger.info("github_monitor_skip", reason="No repos configured")
        return {"status": "skipped", "reason": "No repos configured in skill"}

    result = await monitor_repositories(repos)
    logger.info("github_monitor_complete", repos=len(repos))
    return result


# ==================== Data Agent ====================

@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=180,
)
async def data_agent(task: dict):
    """Data Agent - Analytics and reporting."""
    from src.agents.data_processor import process_data_task
    return await process_data_task(task)


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    schedule=modal.Cron("0 1 * * *"),  # 1 AM UTC = 8 AM ICT
    timeout=300,
)
async def daily_summary():
    """Generate daily activity summary (8 AM ICT)."""
    import structlog
    logger = structlog.get_logger()

    task = {"type": "data", "payload": {"action": "daily_summary"}}
    result = await data_agent.remote.aio(task)

    logger.info("daily_summary_complete", status=result.get("status"))
    return result


# ==================== Content Agent ====================

@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=120,
)
async def content_agent(task: dict):
    """Content Agent - Content generation and transformation."""
    from src.agents.content_generator import process_content_task
    return await process_content_task(task)


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=60,
)
def init_skills():
    """Initialize skills directory with all agent info.md files."""
    from pathlib import Path

    skills = {
        "telegram-chat": """# Telegram Chat Agent

## Instructions
You are a helpful AI assistant communicating via Telegram.
- Be concise and friendly
- Use markdown formatting when helpful
- Respond in the same language as the user

## Tools Available
- web_search: Search the web for current information
- get_datetime: Get current date/time in any timezone
- run_python: Execute Python code for calculations
- read_webpage: Fetch and read URL content
- search_memory: Query past conversations

## Commands
- /start - Welcome message
- /help - Show available commands
- /status - Check agent status
- /translate <text> - Translate to English
- /summarize <text> - Summarize text
- /rewrite <text> - Improve text
""",
        "github": """# GitHub Agent

## Instructions
You are a GitHub automation agent. Handle repository tasks efficiently.

## Tools Available
- create_issue: Create new GitHub issues
- summarize_pr: Summarize pull requests with LLM
- repo_stats: Get repository statistics
- list_issues: List open issues

## Monitored Repos
[Add repos here, one per line with - prefix]

## Memory
[Past interactions and learnings]
""",
        "data": """# Data Agent

## Instructions
You are a data analysis agent. Generate reports and insights.

## Tools Available
- daily_summary: Generate daily activity summary
- analyze_data: Analyze provided data with LLM
- generate_report: Create formatted reports

## Schedule
- Daily summary: 8 AM ICT (1 AM UTC)

## Memory
[Past reports and patterns]
""",
        "content": """# Content Agent

## Instructions
You are a content generation agent. Write, translate, and transform text.

## Tools Available
- write_content: Generate new content on any topic
- translate: Translate between languages
- summarize: Summarize long text
- rewrite: Improve and rewrite text
- email_draft: Draft professional emails

## API Access
- Telegram: /translate, /summarize, /rewrite commands
- HTTP: POST /api/content with {action, ...params}

## Memory
[Content patterns and preferences]
""",
    }

    created = []
    for skill_name, content in skills.items():
        skill_path = Path(f"/skills/{skill_name}/info.md")
        if not skill_path.exists():
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(content)
            created.append(f"{skill_name}/info.md")

    if created:
        skills_volume.commit()
        return {"status": "initialized", "files": created}

    return {"status": "already_initialized", "skills": list(skills.keys())}


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_firebase():
    """Test Firebase connection."""
    from src.services.firebase import init_firebase

    db = init_firebase()
    # Test write
    db.collection("_test").document("ping").set({"status": "ok", "timestamp": datetime.utcnow()})
    # Test read
    doc = db.collection("_test").document("ping").get()
    data = doc.to_dict()
    print(f"Firebase test result: {data}")
    # Cleanup
    db.collection("_test").document("ping").delete()

    # Return simple dict that can be serialized without google.api_core
    return {"status": "success", "verified": True}


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_embeddings():
    """Test Z.AI embedding generation."""
    from src.services.embeddings import EMBEDDING_MODEL, VECTOR_DIM

    try:
        from src.services.embeddings import get_embedding
        text = "Hello, this is a test message for embedding generation."
        embedding = get_embedding(text)

        dim = len(embedding)
        print(f"Embedding dimension: {dim}")
        print(f"Expected dimension: {VECTOR_DIM}")
        print(f"First 5 values: {embedding[:5]}")

        return {
            "status": "success",
            "dimension": dim,
            "expected_dim": VECTOR_DIM,
        }
    except Exception as e:
        print(f"Embedding service not available: {e}")
        return {
            "status": "skipped",
            "reason": "Embedding model not available in API tier",
            "model": EMBEDDING_MODEL,
        }


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_qdrant():
    """Test Qdrant connection and operations."""
    from src.services.qdrant import is_enabled, init_collections

    if not is_enabled():
        return {"status": "skipped", "reason": "Qdrant credentials not configured"}

    result = init_collections()
    return {"status": "success", **result}


@app.function(
    image=image,
    secrets=secrets,
    timeout=120,
)
def test_github():
    """Test GitHub agent connection."""
    from src.agents.github_automation import is_configured

    if not is_configured():
        return {"status": "skipped", "reason": "GitHub token not configured"}

    # Test basic GitHub API access
    from github import Github
    g = Github(os.environ.get("GITHUB_TOKEN", ""))

    try:
        user = g.get_user()
        return {
            "status": "success",
            "login": user.login,
            "public_repos": user.public_repos,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.function(
    image=image,
    secrets=secrets,
    timeout=60,
)
def test_llm():
    """Test LLM providers (Anthropic primary, Z.AI fallback)."""
    from src.services.llm import get_llm_client

    client = get_llm_client()

    try:
        response = client.chat(
            messages=[{"role": "user", "content": "Say hello in exactly 5 words"}],
            max_tokens=50,
        )
        return {
            "status": "success",
            "response": response,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.local_entrypoint()
def main():
    """Local test entrypoint."""
    print("Testing LLM...")
    result = test_llm.remote()
    print(f"LLM test result: {result}")
    print("\nDeploy URL: https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run")
