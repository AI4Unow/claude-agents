# Phase 5: GitHub Agent

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 5 - Telegram Chat Agent](./phase-05-telegram-chat-agent.md)

## Overview

**Priority:** P2 - Feature Agent
**Status:** Pending
**Effort:** 3h

Build GitHub Agent for repository monitoring, issue management, and PR automation. Runs on schedule (cron) and processes tasks from Firebase queue.

## Requirements

### Functional
- Monitor specified repositories for new issues/PRs
- Create issues from Telegram requests
- Summarize PRs and provide review suggestions
- Report repository stats
- Process GitHub-type tasks from Firebase

### Non-Functional
- Hourly cron schedule
- Respect GitHub API rate limits
- Store results in Qdrant for reference

## Capabilities

| Capability | Description | Trigger |
|------------|-------------|---------|
| `create_issue` | Create new GitHub issue | Task from Telegram |
| `summarize_pr` | Summarize PR changes | Task from Telegram |
| `repo_stats` | Get repository statistics | Task from Telegram |
| `monitor_activity` | Check new issues/PRs | Scheduled (hourly) |
| `list_open_issues` | List open issues | Task from Telegram |

## Implementation Steps

### 1. Add GitHub Agent to main.py

```python
# Add to main.py

@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("0 * * * *"),  # Every hour
    timeout=300,
    retries=2,  # Retry on failure (context engineering)
)
async def github_agent_scheduled():
    """GitHub Agent - Scheduled monitoring."""
    from src.agents.github_automation import monitor_repositories
    await monitor_repositories()

@app.function(
    image=image,
    secrets=secrets,
    timeout=120,  # 2 minute max per task (execution limit)
    retries=2,    # Retry on failure
)
async def github_agent_task(task: dict):
    """GitHub Agent - Process single task."""
    from src.agents.github_automation import process_github_task
    return await process_github_task(task)
```

### 2. Create src/agents/github_automation.py

```python
from typing import Dict, List, Optional
from github import Github
import os
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.services import firebase, qdrant, embeddings
from src.services.anthropic import get_claude_response

class GitHubAgent(BaseAgent):
    """GitHub Agent - Repository automation."""

    def __init__(self):
        super().__init__("github")
        self.github = Github(os.environ["GITHUB_TOKEN"])

    async def process(self, task: Dict) -> Dict:
        """Process a GitHub task from queue."""
        action = task.get("payload", {}).get("action", "")
        user_id = task.get("payload", {}).get("user_id")

        handlers = {
            "create_issue": self.create_issue,
            "summarize_pr": self.summarize_pr,
            "repo_stats": self.get_repo_stats,
            "list_issues": self.list_open_issues,
        }

        handler = handlers.get(action, self.handle_unknown_action)
        result = await handler(task.get("payload", {}))

        # Notify user via Telegram if user_id present
        if user_id and result.get("message"):
            await self.notify_user(user_id, result["message"])

        return result

    async def create_issue(self, payload: Dict) -> Dict:
        """Create a new GitHub issue."""
        repo_name = payload.get("repo")
        title = payload.get("title")
        body = payload.get("body", "")

        if not repo_name or not title:
            return {"error": "Missing repo or title"}

        try:
            repo = self.github.get_repo(repo_name)
            issue = repo.create_issue(title=title, body=body)

            await self.log_activity("create_issue", {
                "repo": repo_name,
                "issue_number": issue.number
            })

            return {
                "status": "success",
                "issue_number": issue.number,
                "url": issue.html_url,
                "message": f"✅ Đã tạo issue #{issue.number}: {title}\n{issue.html_url}"
            }
        except Exception as e:
            return {"error": str(e), "message": f"❌ Lỗi tạo issue: {str(e)}"}

    async def summarize_pr(self, payload: Dict) -> Dict:
        """Summarize a pull request."""
        repo_name = payload.get("repo")
        pr_number = payload.get("pr_number")

        if not repo_name or not pr_number:
            return {"error": "Missing repo or pr_number"}

        try:
            repo = self.github.get_repo(repo_name)
            pr = repo.get_pull(int(pr_number))

            # Get PR details
            files_changed = list(pr.get_files())
            file_summary = "\n".join([
                f"- {f.filename} (+{f.additions}/-{f.deletions})"
                for f in files_changed[:20]  # Limit to 20 files
            ])

            # Use Claude to summarize
            summary = await get_claude_response(
                user_message=f"""Summarize this Pull Request:

Title: {pr.title}
Description: {pr.body or 'No description'}

Files changed:
{file_summary}

Provide a brief summary of what this PR does and any potential concerns.""",
                system_prompt="You are a code review assistant. Be concise and technical."
            )

            # Store in Qdrant for future reference
            embedding = embeddings.get_embedding(summary)
            await qdrant.store_task_context(
                task_id=f"pr_{repo_name}_{pr_number}",
                task_type="github",
                summary=summary,
                result={"repo": repo_name, "pr": pr_number},
                embedding=embedding
            )

            return {
                "status": "success",
                "summary": summary,
                "message": f"📋 PR #{pr_number} Summary:\n\n{summary}"
            }
        except Exception as e:
            return {"error": str(e), "message": f"❌ Lỗi: {str(e)}"}

    async def get_repo_stats(self, payload: Dict) -> Dict:
        """Get repository statistics."""
        repo_name = payload.get("repo")

        if not repo_name:
            return {"error": "Missing repo"}

        try:
            repo = self.github.get_repo(repo_name)

            stats = {
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "watchers": repo.watchers_count,
                "language": repo.language,
            }

            # Get recent activity
            commits = list(repo.get_commits()[:5])
            recent_commits = [
                f"- {c.commit.message.split(chr(10))[0][:50]}"
                for c in commits
            ]

            message = f"""📊 **{repo_name}** Stats:
⭐ Stars: {stats['stars']}
🍴 Forks: {stats['forks']}
🐛 Open Issues: {stats['open_issues']}
📝 Language: {stats['language']}

Recent commits:
{chr(10).join(recent_commits)}"""

            return {"status": "success", "stats": stats, "message": message}
        except Exception as e:
            return {"error": str(e), "message": f"❌ Lỗi: {str(e)}"}

    async def list_open_issues(self, payload: Dict) -> Dict:
        """List open issues for a repository."""
        repo_name = payload.get("repo")
        limit = payload.get("limit", 10)

        if not repo_name:
            return {"error": "Missing repo"}

        try:
            repo = self.github.get_repo(repo_name)
            issues = list(repo.get_issues(state="open")[:limit])

            issue_list = [
                f"#{i.number}: {i.title}"
                for i in issues
            ]

            message = f"""📝 Open issues in **{repo_name}**:

{chr(10).join(issue_list) if issue_list else 'No open issues'}"""

            return {
                "status": "success",
                "count": len(issues),
                "issues": issue_list,
                "message": message
            }
        except Exception as e:
            return {"error": str(e), "message": f"❌ Lỗi: {str(e)}"}

    async def handle_unknown_action(self, payload: Dict) -> Dict:
        """Handle unknown action."""
        return {"error": "Unknown action", "message": "❌ Action không được hỗ trợ"}

    async def notify_user(self, user_id: str, message: str):
        """
        Notify user via Telegram using forward_to_user pattern.

        Uses direct forwarding to prevent "telephone game" data loss
        where supervisor paraphrases responses incorrectly.
        """
        # Use inherited forward_to_user from BaseAgent
        await self.forward_to_user(
            user_id=user_id,
            message=message,
            bypass_supervisor=True  # Send directly, don't paraphrase
        )


# ==================== Scheduled Functions ====================

async def monitor_repositories():
    """Monitor configured repositories for new activity."""
    agent = GitHubAgent()
    await agent.update_status("running")

    # Get monitored repos from config
    config = await firebase.get_agent("github")
    repos_to_monitor = config.get("config", {}).get("repos", [])

    for repo_name in repos_to_monitor:
        try:
            repo = agent.github.get_repo(repo_name)

            # Check for new issues in last hour
            since = datetime.utcnow() - timedelta(hours=1)
            new_issues = [
                i for i in repo.get_issues(state="open", since=since)
            ]

            if new_issues:
                await agent.log_activity("new_issues_found", {
                    "repo": repo_name,
                    "count": len(new_issues)
                })

        except Exception as e:
            await agent.log_activity("monitor_error", {
                "repo": repo_name,
                "error": str(e)
            }, level="error")

    await agent.update_status("idle")


async def process_github_task(task: Dict) -> Dict:
    """Process a single GitHub task."""
    agent = GitHubAgent()
    await agent.update_status("running")

    try:
        result = await agent.process(task)
        await firebase.complete_task(task["id"], result)
    except Exception as e:
        await firebase.fail_task(task["id"], str(e))
        result = {"error": str(e)}

    await agent.update_status("idle")
    return result
```

### 3. Add Task Processor Loop

```python
# Add to main.py

@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
)
async def process_github_queue():
    """Process pending GitHub tasks from queue."""
    from src.services import firebase
    from src.agents.github_automation import process_github_task

    while True:
        task = await firebase.claim_task("github", "github-processor")
        if not task:
            break  # No more tasks

        await process_github_task(task)
```

### 4. Configure Monitored Repos in Firebase

```python
# One-time setup via Firebase Console or script
db.collection("agents").document("github").set({
    "type": "github",
    "status": "idle",
    "config": {
        "repos": [
            "owner/repo1",
            "owner/repo2"
        ]
    }
})
```

## Files to Create

| Path | Action | Description |
|------|--------|-------------|
| `agents/src/agents/github_automation.py` | Create | GitHub Agent implementation |

## Todo List

- [ ] Add GitHub functions to main.py
- [ ] Create github_automation.py agent
- [ ] Configure GitHub token in Modal secrets
- [ ] Set up monitored repos in Firebase
- [ ] Deploy and test cron schedule
- [ ] Test task delegation from Telegram
- [ ] Verify notifications work

## Success Criteria

- [ ] Cron runs hourly without errors
- [ ] Tasks from Firebase processed correctly
- [ ] Issues can be created via Telegram
- [ ] PR summaries generated correctly
- [ ] User notifications delivered

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| GitHub rate limit | API blocked | Respect limits, caching |
| Invalid repo access | 404 errors | Validate repo access upfront |
| Large PR diffs | Timeout | Limit file count, truncate |

## Security Considerations

- GitHub token with minimal permissions (repo read/write only)
- Never expose token in logs
- Validate repo names from user input

## Next Steps

After completing this phase:
1. Proceed to Phase 6: Data & Content Agents
2. Test full flow: Telegram → GitHub → Telegram notification
