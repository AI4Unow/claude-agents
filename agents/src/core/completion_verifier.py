"""Completion Verifier - Programmatically verify task completion where possible.

Checks meeting attendance, API callbacks, location data to auto-verify tasks.
"""
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict

from src.services.firebase.pkm import SmartTask
from src.utils.logging import get_logger

logger = get_logger()


class CompletionVerifier:
    """Verify task completion programmatically where possible."""

    VERIFIABLE_PATTERNS = {
        "meeting": r"(?:meet|call|sync|standup|1:1|1-on-1|one on one)",
        "email": r"(?:email|mail|send to|send an email)",
        "api_call": r"(?:deploy|push|merge|release|publish)",
        "location": r"(?:go to|visit|pick up from|drop off at|arrive at)",
    }

    def __init__(self):
        self.compiled_patterns = {
            vtype: re.compile(pattern, re.IGNORECASE)
            for vtype, pattern in self.VERIFIABLE_PATTERNS.items()
        }

    async def can_verify(self, task: SmartTask) -> Optional[str]:
        """Check if task can be auto-verified. Returns verification type.

        Args:
            task: SmartTask to check

        Returns:
            Verification type string if verifiable, None otherwise
        """
        for vtype, pattern in self.compiled_patterns.items():
            if pattern.search(task.content):
                logger.debug("verifiable_task_detected", task_id=task.id, type=vtype)
                return vtype

        return None

    async def verify(
        self,
        task: SmartTask,
        verification_type: str,
        context: Optional[Dict] = None
    ) -> bool:
        """Attempt to verify task completion.

        Args:
            task: SmartTask to verify
            verification_type: Type of verification (meeting, email, api_call, location)
            context: Optional context data (calendar_events, api_status, etc.)

        Returns:
            True if verified complete, False otherwise
        """
        context = context or {}

        if verification_type == "meeting":
            return await self._verify_meeting_held(task, context.get("calendar_events", []))

        elif verification_type == "email":
            # Would need email API integration
            logger.debug("email_verification_not_implemented", task_id=task.id)
            return False

        elif verification_type == "api_call":
            return await self._verify_api_action(task, context)

        elif verification_type == "location":
            # Would need location API
            logger.debug("location_verification_not_implemented", task_id=task.id)
            return False

        return False

    async def _verify_meeting_held(
        self,
        task: SmartTask,
        calendar_events: List[Dict]
    ) -> bool:
        """Check if meeting occurred based on calendar.

        Args:
            task: SmartTask
            calendar_events: List of calendar events

        Returns:
            True if meeting found and ended
        """
        now = datetime.now(timezone.utc)

        # Extract meeting keywords from task
        keywords = self._extract_keywords(task.content)

        logger.debug(
            "verifying_meeting",
            task_id=task.id,
            keywords=keywords,
            events_count=len(calendar_events)
        )

        for event in calendar_events:
            event_end = event.get("end")
            if not event_end:
                continue

            # Ensure timezone aware
            if event_end.tzinfo is None:
                event_end = event_end.replace(tzinfo=timezone.utc)

            # Event has ended
            if event_end < now:
                event_title = event.get("summary", "").lower()

                # Check if any keyword matches
                if any(kw.lower() in event_title for kw in keywords):
                    logger.info(
                        "meeting_verified",
                        task_id=task.id,
                        event_title=event.get("summary"),
                        event_end=event_end.isoformat()
                    )
                    return True

        logger.debug("meeting_not_verified", task_id=task.id)
        return False

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from task text.

        Args:
            text: Task content

        Returns:
            List of keywords
        """
        # Remove common words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "with", "about", "meet", "call", "have", "schedule", "join", "attend"
        }

        # Split and clean
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        # Return top 5 most distinctive keywords
        return keywords[:5]

    async def _verify_api_action(
        self,
        task: SmartTask,
        context: Dict
    ) -> bool:
        """Check if API action completed (deploy, merge, release, etc.).

        Args:
            task: SmartTask
            context: Context with API status data

        Returns:
            True if action verified
        """
        # Extract action type
        action_type = None
        if "deploy" in task.content.lower():
            action_type = "deploy"
        elif "merge" in task.content.lower():
            action_type = "merge"
        elif "release" in task.content.lower():
            action_type = "release"
        elif "publish" in task.content.lower():
            action_type = "publish"

        if not action_type:
            return False

        logger.debug("verifying_api_action", task_id=task.id, action_type=action_type)

        # Check if context has verification data
        if action_type == "deploy":
            return self._check_deployment_status(task, context)
        elif action_type == "merge":
            return self._check_pr_merged(task, context)
        elif action_type in ["release", "publish"]:
            return self._check_release_published(task, context)

        return False

    def _check_deployment_status(self, task: SmartTask, context: Dict) -> bool:
        """Check deployment status from context.

        Args:
            task: SmartTask
            context: Context data

        Returns:
            True if deployment verified
        """
        # Look for deployment status in context
        deployments = context.get("deployments", [])

        if not deployments:
            return False

        # Extract project/service name from task
        keywords = self._extract_keywords(task.content)

        for deploy in deployments:
            deploy_name = deploy.get("name", "").lower()
            deploy_status = deploy.get("status", "").lower()
            deploy_time = deploy.get("completed_at")

            # Check if deployment matches task keywords
            if any(kw.lower() in deploy_name for kw in keywords):
                # Check if completed after task creation
                if deploy_status in ["success", "completed"]:
                    if task.created_at and deploy_time:
                        if deploy_time > task.created_at:
                            logger.info(
                                "deployment_verified",
                                task_id=task.id,
                                deploy_name=deploy.get("name")
                            )
                            return True

        return False

    def _check_pr_merged(self, task: SmartTask, context: Dict) -> bool:
        """Check if PR was merged from context.

        Args:
            task: SmartTask
            context: Context data

        Returns:
            True if PR merge verified
        """
        pull_requests = context.get("pull_requests", [])

        if not pull_requests:
            return False

        keywords = self._extract_keywords(task.content)

        for pr in pull_requests:
            pr_title = pr.get("title", "").lower()
            pr_state = pr.get("state", "").lower()
            pr_merged_at = pr.get("merged_at")

            # Check if PR matches task
            if any(kw.lower() in pr_title for kw in keywords):
                if pr_state == "merged" or pr_merged_at:
                    if task.created_at and pr_merged_at:
                        if pr_merged_at > task.created_at:
                            logger.info(
                                "pr_merge_verified",
                                task_id=task.id,
                                pr_title=pr.get("title")
                            )
                            return True

        return False

    def _check_release_published(self, task: SmartTask, context: Dict) -> bool:
        """Check if release was published from context.

        Args:
            task: SmartTask
            context: Context data

        Returns:
            True if release verified
        """
        releases = context.get("releases", [])

        if not releases:
            return False

        keywords = self._extract_keywords(task.content)

        for release in releases:
            release_name = release.get("name", "").lower()
            release_published = release.get("published_at")

            # Check if release matches task
            if any(kw.lower() in release_name for kw in keywords):
                if task.created_at and release_published:
                    if release_published > task.created_at:
                        logger.info(
                            "release_verified",
                            task_id=task.id,
                            release_name=release.get("name")
                        )
                        return True

        return False

    async def verify_and_mark_complete(
        self,
        task: SmartTask,
        context: Optional[Dict] = None
    ) -> bool:
        """Attempt verification and mark task complete if verified.

        Args:
            task: SmartTask to verify
            context: Optional verification context

        Returns:
            True if verified and marked complete
        """
        verification_type = await self.can_verify(task)

        if not verification_type:
            logger.debug("task_not_verifiable", task_id=task.id)
            return False

        verified = await self.verify(task, verification_type, context)

        if verified:
            # Mark task as complete
            from src.services.firebase.pkm import update_smart_task

            await update_smart_task(
                task.user_id,
                task.id,
                status="done"
            )

            logger.info(
                "task_auto_completed",
                task_id=task.id,
                verification_type=verification_type
            )

            return True

        return False
