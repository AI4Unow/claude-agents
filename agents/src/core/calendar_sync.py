"""Calendar sync orchestration manager.

Coordinates bidirectional sync across Google Calendar, Google Tasks, and Apple CalDAV.
Firebase remains the source of truth for conflict resolution.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional

from src.services.google_calendar import GoogleCalendarService
from src.services.google_tasks import GoogleTasksService
from src.services.apple_caldav import AppleCalDAVService
from src.utils.logging import get_logger

logger = get_logger()


# Security: Patterns for sensitive data in error messages
SENSITIVE_PATTERNS = [
    r'Bearer\s+[\w\-\.]+',
    r'access_token["\':\s=]+[\w\-\.]+',
    r'refresh_token["\':\s=]+[\w\-\.]+',
    r'client_secret["\':\s=]+[\w\-\.]+',
    r'api_key["\':\s=]+[\w\-\.]+',
    r'password["\':\s=]+\S+',
]


def sanitize_error(error_str: str, max_length: int = 200) -> str:
    """Sanitize error message to remove sensitive data.

    Args:
        error_str: Raw error message
        max_length: Maximum length of output

    Returns:
        Sanitized error string
    """
    if not error_str:
        return ""

    result = str(error_str)
    for pattern in SENSITIVE_PATTERNS:
        result = re.sub(pattern, '[REDACTED]', result, flags=re.IGNORECASE)

    return result[:max_length]


@dataclass
class SyncStatus:
    """Sync status for a user across all calendar services."""

    user_id: int
    google_calendar: Literal["connected", "disconnected", "error"]
    google_tasks: Literal["connected", "disconnected", "error"]
    apple_caldav: Literal["connected", "disconnected", "error"]
    last_sync: Optional[datetime]
    pending_conflicts: int


@dataclass
class SyncResult:
    """Result of syncing a single task to calendar services."""

    task_id: str
    google_calendar: bool
    google_tasks: bool
    apple_caldav: bool
    errors: List[str]


class CalendarSyncManager:
    """Orchestrate sync across all calendar services."""

    def __init__(self):
        """Initialize sync manager."""
        self.logger = logger.bind(component="CalendarSyncManager")

    async def sync_task(
        self,
        task: Dict,
        user_settings: Dict,
        credentials: Dict
    ) -> SyncResult:
        """Sync task to enabled calendar services.

        Args:
            task: SmartTask dict
            user_settings: User calendar sync settings
            credentials: Dict with OAuth tokens for each service

        Returns:
            SyncResult with status for each service
        """
        result = SyncResult(
            task_id=task.get("id", "unknown"),
            google_calendar=False,
            google_tasks=False,
            apple_caldav=False,
            errors=[]
        )

        # Google Calendar sync
        if user_settings.get("google_calendar_enabled"):
            try:
                gcal_creds = credentials.get("google_calendar")
                if gcal_creds:
                    result.google_calendar = await self._sync_google_calendar(task, gcal_creds)
                else:
                    result.errors.append("google_calendar: missing credentials")

            except Exception as e:
                error_msg = f"google_calendar: {sanitize_error(str(e))}"
                result.errors.append(error_msg)
                self.logger.error("google_calendar_sync_failed", task_id=task.get("id"), error=sanitize_error(str(e)))

        # Google Tasks sync
        if user_settings.get("google_tasks_enabled"):
            try:
                gtasks_creds = credentials.get("google_tasks")
                if gtasks_creds:
                    result.google_tasks = await self._sync_google_tasks(task, gtasks_creds)
                else:
                    result.errors.append("google_tasks: missing credentials")

            except Exception as e:
                error_msg = f"google_tasks: {sanitize_error(str(e))}"
                result.errors.append(error_msg)
                self.logger.error("google_tasks_sync_failed", task_id=task.get("id"), error=sanitize_error(str(e)))

        # Apple CalDAV sync
        if user_settings.get("apple_caldav_enabled"):
            try:
                apple_creds = credentials.get("apple_caldav")
                if apple_creds:
                    result.apple_caldav = await self._sync_apple_caldav(task, apple_creds)
                else:
                    result.errors.append("apple_caldav: missing credentials")

            except Exception as e:
                error_msg = f"apple_caldav: {sanitize_error(str(e))}"
                result.errors.append(error_msg)
                self.logger.error("apple_caldav_sync_failed", task_id=task.get("id"), error=sanitize_error(str(e)))

        self.logger.info(
            "task_synced",
            task_id=task.get("id"),
            google_calendar=result.google_calendar,
            google_tasks=result.google_tasks,
            apple_caldav=result.apple_caldav,
            errors_count=len(result.errors)
        )

        return result

    async def _sync_google_calendar(self, task: Dict, credentials) -> bool:
        """Sync task to Google Calendar.

        Args:
            task: SmartTask dict
            credentials: Google OAuth2 credentials

        Returns:
            True if successful
        """
        from google.oauth2.credentials import Credentials

        # Build credentials object
        creds = Credentials(
            token=credentials["access_token"],
            refresh_token=credentials.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret")
        )

        gcal = GoogleCalendarService(creds)

        if task.get("google_event_id"):
            # Update existing event
            success, new_etag = await gcal.update_event(
                task["google_event_id"],
                task,
                etag=task.get("google_event_etag")
            )
            if success and new_etag:
                # Store new ETag (caller should update Firebase)
                task["google_event_etag"] = new_etag
            return success
        else:
            # Create new event
            event_id = await gcal.create_event(task)
            if event_id:
                # Store event ID (caller should update Firebase)
                task["google_event_id"] = event_id
                return True
            return False

    async def _sync_google_tasks(self, task: Dict, credentials) -> bool:
        """Sync task to Google Tasks.

        Args:
            task: SmartTask dict
            credentials: Google OAuth2 credentials

        Returns:
            True if successful
        """
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=credentials["access_token"],
            refresh_token=credentials.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret")
        )

        gtasks = GoogleTasksService(creds)

        if task.get("google_task_id"):
            # Update existing task
            return await gtasks.update_task(task["google_task_id"], task)
        else:
            # Create new task
            task_id = await gtasks.create_task(task)
            if task_id:
                task["google_task_id"] = task_id
                return True
            return False

    async def _sync_apple_caldav(self, task: Dict, credentials: Dict) -> bool:
        """Sync task to Apple CalDAV.

        Args:
            task: SmartTask dict
            credentials: Apple CalDAV credentials (apple_id, app_password)

        Returns:
            True if successful
        """
        apple = AppleCalDAVService(
            credentials["apple_id"],
            credentials["app_password"]
        )

        # Connect first
        connected = await apple.connect()
        if not connected:
            return False

        if task.get("apple_uid"):
            # Update existing event
            return await apple.update_event(task["apple_uid"], task)
        else:
            # Create new event
            uid = await apple.create_event(task)
            if uid:
                task["apple_uid"] = uid
                return True
            return False

    async def handle_external_change(
        self,
        source: Literal["google_calendar", "google_tasks", "apple_caldav"],
        event_data: Dict,
        user_id: int,
        firebase_task_getter: callable,
        firebase_task_updater: callable
    ) -> None:
        """Handle change from external calendar.

        Firebase wins all conflicts (source of truth).

        Args:
            source: Which calendar service triggered the change
            event_data: Event data from external calendar
            user_id: User ID
            firebase_task_getter: Async function to get SmartTask by external ID
            firebase_task_updater: Async function to update SmartTask
        """
        try:
            # Find matching SmartTask
            task = await firebase_task_getter(source, event_data.get("id"), user_id)

            if not task:
                self.logger.debug(
                    "external_event_ignored",
                    source=source,
                    event_id=event_data.get("id"),
                    reason="no_matching_task"
                )
                return

            # Compare timestamps
            external_updated = event_data.get("updated")
            firebase_updated = task.get("updated_at")

            if not external_updated or not firebase_updated:
                # Can't compare timestamps, skip
                self.logger.warning(
                    "timestamp_comparison_failed",
                    source=source,
                    event_id=event_data.get("id"),
                    has_external=bool(external_updated),
                    has_firebase=bool(firebase_updated)
                )
                return

            # Parse external timestamp
            if isinstance(external_updated, str):
                external_updated = datetime.fromisoformat(external_updated.replace("Z", "+00:00"))

            # Compare: Firebase wins if newer
            if firebase_updated > external_updated:
                self.logger.info(
                    "firebase_wins_conflict",
                    source=source,
                    event_id=event_data.get("id"),
                    task_id=task.get("id"),
                    firebase_time=firebase_updated.isoformat(),
                    external_time=external_updated.isoformat()
                )
                # TODO: Push Firebase state back to external calendar
                # (requires credentials from user_settings)
                return

            # External is newer - update Firebase
            updates = {}

            if event_data.get("summary"):
                updates["content"] = event_data["summary"]

            if event_data.get("start"):
                start_dt = event_data["start"]
                if isinstance(start_dt, str):
                    start_dt = datetime.fromisoformat(start_dt.replace("Z", "+00:00"))
                updates["due_date"] = start_dt.date()
                if start_dt.time() != datetime.min.time():
                    updates["due_time"] = start_dt.time()

            if updates:
                await firebase_task_updater(user_id, task["id"], **updates)
                self.logger.info(
                    "firebase_updated_from_external",
                    source=source,
                    event_id=event_data.get("id"),
                    task_id=task.get("id"),
                    updates=list(updates.keys())
                )

        except Exception as e:
            self.logger.error(
                "external_change_handling_failed",
                source=source,
                event_id=event_data.get("id"),
                error=sanitize_error(str(e))
            )

    async def get_sync_status(
        self,
        user_id: int,
        user_settings: Dict,
        conflict_counter: callable
    ) -> SyncStatus:
        """Get current sync status for user.

        Args:
            user_id: User ID
            user_settings: User calendar sync settings
            conflict_counter: Async function to count pending conflicts

        Returns:
            SyncStatus object
        """
        try:
            conflicts = await conflict_counter(user_id)
        except Exception as e:
            self.logger.error("conflict_count_failed", user_id=user_id, error=sanitize_error(str(e), 50))
            conflicts = 0

        return SyncStatus(
            user_id=user_id,
            google_calendar="connected" if user_settings.get("google_calendar_enabled") else "disconnected",
            google_tasks="connected" if user_settings.get("google_tasks_enabled") else "disconnected",
            apple_caldav="connected" if user_settings.get("apple_caldav_enabled") else "disconnected",
            last_sync=user_settings.get("last_calendar_sync"),
            pending_conflicts=conflicts
        )

    async def delete_from_calendars(
        self,
        task: Dict,
        user_settings: Dict,
        credentials: Dict
    ) -> Dict[str, bool]:
        """Delete task from all connected calendar services.

        Args:
            task: SmartTask dict with external IDs
            user_settings: User calendar sync settings
            credentials: OAuth credentials for each service

        Returns:
            Dict with deletion status for each service
        """
        results = {}

        # Google Calendar
        if user_settings.get("google_calendar_enabled") and task.get("google_event_id"):
            try:
                gcal_creds = credentials.get("google_calendar")
                if gcal_creds:
                    from google.oauth2.credentials import Credentials
                    creds = Credentials(token=gcal_creds["access_token"])
                    gcal = GoogleCalendarService(creds)
                    results["google_calendar"] = await gcal.delete_event(task["google_event_id"])
            except Exception as e:
                self.logger.error("google_calendar_delete_failed", error=sanitize_error(str(e)))
                results["google_calendar"] = False

        # Google Tasks
        if user_settings.get("google_tasks_enabled") and task.get("google_task_id"):
            try:
                gtasks_creds = credentials.get("google_tasks")
                if gtasks_creds:
                    from google.oauth2.credentials import Credentials
                    creds = Credentials(token=gtasks_creds["access_token"])
                    gtasks = GoogleTasksService(creds)
                    results["google_tasks"] = await gtasks.delete_task(task["google_task_id"])
            except Exception as e:
                self.logger.error("google_tasks_delete_failed", error=sanitize_error(str(e)))
                results["google_tasks"] = False

        # Apple CalDAV
        if user_settings.get("apple_caldav_enabled") and task.get("apple_uid"):
            try:
                apple_creds = credentials.get("apple_caldav")
                if apple_creds:
                    apple = AppleCalDAVService(
                        apple_creds["apple_id"],
                        apple_creds["app_password"]
                    )
                    await apple.connect()
                    results["apple_caldav"] = await apple.delete_event(task["apple_uid"])
            except Exception as e:
                self.logger.error("apple_caldav_delete_failed", error=sanitize_error(str(e)))
                results["apple_caldav"] = False

        return results
