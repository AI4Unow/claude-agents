# Phase 1: GitHub Agent Deployment

## Context
- [Plan Overview](./plan.md)
- Agent code exists: `src/agents/github_automation.py`

## Overview

Deploy GitHubAgent as Modal function with webhook and cron triggers.

## Requirements

1. Create Modal function `github_agent()` in main.py
2. Create `skills/github/info.md` skill file
3. Add webhook endpoint `/webhook/github`
4. Optional: Add cron schedule for repo monitoring

## Implementation

### 1. Add Modal Function to main.py

```python
@app.function(
    image=image,
    secrets=secrets + [modal.Secret.from_name("github-credentials")],
    volumes={"/skills": skills_volume},
    timeout=120,
)
async def github_agent(task: Dict):
    """GitHub Agent - Repository automation."""
    from src.agents.github_automation import process_github_task
    return await process_github_task(task)
```

### 2. Add Webhook to create_web_app()

```python
@web_app.post("/webhook/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    task = {
        "type": "github",
        "payload": {
            "event": event,
            "data": payload
        }
    }

    result = await github_agent.remote.aio(task)
    return result
```

### 3. Create Skill File

Create `skills/github/info.md`:

```markdown
# GitHub Agent

## Instructions
You are a GitHub automation agent. Handle repository tasks efficiently.

## Tools Available
- Create issues
- Summarize PRs
- Get repo stats
- List open issues
- Monitor repositories

## Memory
[Past interactions and learnings]
```

## Todo
- [ ] Add github_agent() function to main.py
- [ ] Add /webhook/github endpoint
- [ ] Create skills/github/info.md
- [ ] Add github-credentials secret if needed
- [ ] Deploy and test

## Success Criteria

1. `github_agent` appears in Modal app functions
2. `/webhook/github` endpoint responds
3. Can process GitHub events (issue creation, PR summary)
