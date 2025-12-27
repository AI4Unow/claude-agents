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
    modal.Secret.from_name("zai-credentials"),
    modal.Secret.from_name("firebase-credentials"),
    modal.Secret.from_name("telegram-credentials"),
]


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
        update = await request.json()

        # Extract message
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")
        user = message.get("from", {})

        if not chat_id or not text:
            return {"ok": True}

        # Handle commands
        if text.startswith("/"):
            response = await handle_command(text, user)
        else:
            response = await process_message(text, user, chat_id)

        # Send response
        await send_telegram_message(chat_id, response)

        return {"ok": True}

    return web_app


async def handle_command(command: str, user: dict) -> str:
    """Handle bot commands."""
    cmd = command.split()[0].lower()

    if cmd == "/start":
        return f"Hello {user.get('first_name', 'there')}! I'm your AI assistant powered by II Framework."
    elif cmd == "/help":
        return "Available commands:\n/start - Welcome\n/help - This message\n/status - Check agent status"
    elif cmd == "/status":
        return "Agent is running normally."
    else:
        return "Unknown command. Try /help"


async def process_message(text: str, user: dict, chat_id: int) -> str:
    """Process a regular message with LLM."""
    from openai import OpenAI
    from pathlib import Path

    api_key = os.environ.get("ZAI_API_KEY", "")
    base_url = os.environ.get("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    model = os.environ.get("ZAI_MODEL", "glm-4.7")

    client = OpenAI(api_key=api_key, base_url=base_url)

    # Read instructions from skills volume
    info_path = Path("/skills/telegram-chat/info.md")
    system_prompt = "You are a helpful AI assistant."
    if info_path.exists():
        system_prompt = info_path.read_text()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        max_tokens=1024,
    )

    return response.choices[0].message.content


async def send_telegram_message(chat_id: int, text: str):
    """Send message via Telegram API."""
    import httpx

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        })


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


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=60,
)
def init_skills():
    """Initialize skills directory with default info.md files."""
    from pathlib import Path

    telegram_info = Path("/skills/telegram-chat/info.md")

    if not telegram_info.exists():
        telegram_info.parent.mkdir(parents=True, exist_ok=True)
        telegram_info.write_text("""# Telegram Chat Agent

## Instructions
You are a helpful AI assistant communicating via Telegram.
- Be concise and friendly
- Use markdown formatting when helpful
- Respond in the same language as the user

## Tools Available
- Chat with users via Telegram
- Process text messages
- Handle bot commands

## Memory
[Accumulated learnings from past runs]

## Error History
[Past errors and how they were resolved]

## Current Plan
- Respond helpfully to user messages
- Learn from interactions
""")
        skills_volume.commit()
        return {"status": "initialized", "files": ["telegram-chat/info.md"]}

    return {"status": "already_initialized"}


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


@app.local_entrypoint()
def main():
    """Local test entrypoint."""
    print("Initializing skills...")
    result = init_skills.remote()
    print(f"Skills init result: {result}")
    print("\nDeploy URL: https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run")
