"""GitHub Agent - Repository automation.

Handles GitHub operations like issue creation, PR summarization,
and repository monitoring. Requires GITHUB_TOKEN in Modal secrets.
"""
from typing import Dict, List, Optional
import os
from datetime import datetime, timedelta

from src.utils.logging import get_logger
from src.agents.base import BaseAgent

logger = get_logger()


def is_configured() -> bool:
    """Check if GitHub token is configured."""
    return bool(os.environ.get("GITHUB_TOKEN"))


class GitHubAgent(BaseAgent):
    """GitHub Agent - Repository automation."""

    def __init__(self):
        super().__init__("github")
        self._github = None

    @property
    def github(self):
        """Lazy-load GitHub client."""
        if self._github is None:
            from github import Github
            token = os.environ.get("GITHUB_TOKEN", "")
            self._github = Github(token)
        return self._github

    async def process(self, task: Dict) -> Dict:
        """Process a GitHub task from queue."""
        if not is_configured():
            return {"error": "GitHub token not configured", "status": "skipped"}

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
                "message": f"✅ Created issue #{issue.number}: {title}\n{issue.html_url}"
            }
        except Exception as e:
            logger.error("create_issue_error", error=str(e), repo=repo_name)
            return {"error": str(e), "message": f"❌ Error creating issue: {str(e)}"}

    async def summarize_pr(self, payload: Dict) -> Dict:
        """Summarize a pull request using LLM."""
        repo_name = payload.get("repo")
        pr_number = payload.get("pr_number")

        if not repo_name or not pr_number:
            return {"error": "Missing repo or pr_number"}

        try:
            repo = self.github.get_repo(repo_name)
            pr = repo.get_pull(int(pr_number))

            # Get PR details
            files_changed = list(pr.get_files())[:20]  # Limit to 20 files
            file_summary = "\n".join([
                f"- {f.filename} (+{f.additions}/-{f.deletions})"
                for f in files_changed
            ])

            # Use LLM to summarize
            prompt = f"""Summarize this Pull Request:

Title: {pr.title}
Description: {pr.body or 'No description'}

Files changed:
{file_summary}

Provide a brief summary of what this PR does and any potential concerns."""

            summary = self.execute_with_llm(prompt)

            return {
                "status": "success",
                "summary": summary,
                "message": f"📋 PR #{pr_number} Summary:\n\n{summary}"
            }
        except Exception as e:
            logger.error("summarize_pr_error", error=str(e))
            return {"error": str(e), "message": f"❌ Error: {str(e)}"}

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
            logger.error("repo_stats_error", error=str(e))
            return {"error": str(e), "message": f"❌ Error: {str(e)}"}

    async def list_open_issues(self, payload: Dict) -> Dict:
        """List open issues for a repository."""
        repo_name = payload.get("repo")
        limit = payload.get("limit", 10)

        if not repo_name:
            return {"error": "Missing repo"}

        try:
            repo = self.github.get_repo(repo_name)
            issues = list(repo.get_issues(state="open"))[:limit]

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
            logger.error("list_issues_error", error=str(e))
            return {"error": str(e), "message": f"❌ Error: {str(e)}"}

    async def handle_unknown_action(self, payload: Dict) -> Dict:
        """Handle unknown action."""
        return {"error": "Unknown action", "message": "❌ Action not supported"}


# ==================== Task Processing ====================

async def process_github_task(task: Dict) -> Dict:
    """Process a single GitHub task."""
    if not is_configured():
        return {"status": "skipped", "reason": "GitHub token not configured"}

    agent = GitHubAgent()

    try:
        result = await agent.process(task)
        return result
    except Exception as e:
        logger.error("github_task_error", error=str(e))
        return {"error": str(e)}


async def monitor_repositories(repos: List[str] = None) -> Dict:
    """Monitor configured repositories for new activity."""
    if not is_configured():
        return {"status": "skipped", "reason": "GitHub token not configured"}

    agent = GitHubAgent()
    results = []

    repos_to_monitor = repos or []

    for repo_name in repos_to_monitor:
        try:
            repo = agent.github.get_repo(repo_name)

            # Check for new issues in last hour
            since = datetime.utcnow() - timedelta(hours=1)
            new_issues = [
                i for i in repo.get_issues(state="open", since=since)
            ]

            results.append({
                "repo": repo_name,
                "new_issues": len(new_issues),
            })

        except Exception as e:
            logger.error("monitor_error", repo=repo_name, error=str(e))
            results.append({
                "repo": repo_name,
                "error": str(e),
            })

    return {"status": "success", "results": results}
