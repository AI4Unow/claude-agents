"""Google Tasks API wrapper with shadow recurrence system.

Google Tasks API doesn't support recurrence natively, so we store RRULE in notes field
and create next instance on completion.
"""
import re
from datetime import datetime, timezone, time
from typing import Dict, List, Optional

from dateutil.rrule import rrulestr
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils.logging import get_logger

logger = get_logger()


# Security: RRULE validation to prevent DoS attacks
ALLOWED_FREQ = {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}
MAX_RRULE_COUNT = 365  # Maximum recurrence count


def validate_rrule(rrule_str: str) -> bool:
    """Validate RRULE string to prevent DoS attacks.

    Blocks:
    - SECONDLY/MINUTELY/HOURLY frequencies (too frequent)
    - COUNT > 365 (unbounded iterations)
    - Malformed RRULE strings

    Args:
        rrule_str: RRULE string without "RRULE:" prefix

    Returns:
        True if valid and safe
    """
    if not rrule_str or len(rrule_str) > 500:
        return False

    # Block dangerous frequencies
    if re.search(r'FREQ=(SECONDLY|MINUTELY|HOURLY)', rrule_str, re.IGNORECASE):
        return False

    # Check for valid frequency
    freq_match = re.search(r'FREQ=(\w+)', rrule_str, re.IGNORECASE)
    if not freq_match or freq_match.group(1).upper() not in ALLOWED_FREQ:
        return False

    # Limit COUNT to prevent DoS
    count_match = re.search(r'COUNT=(\d+)', rrule_str)
    if count_match and int(count_match.group(1)) > MAX_RRULE_COUNT:
        return False

    return True


class GoogleTasksService:
    """Google Tasks API with shadow recurrence system."""

    SCOPES = ["https://www.googleapis.com/auth/tasks"]
    TASKLIST_TITLE = "ai4u Tasks"

    def __init__(self, credentials: Credentials):
        """Initialize Google Tasks service.

        Args:
            credentials: OAuth2 credentials from Google
        """
        self.service = build("tasks", "v1", credentials=credentials)
        self._tasklist_id: Optional[str] = None
        self.logger = logger.bind(service="google_tasks")

    async def ensure_tasklist(self) -> str:
        """Get or create ai4u Tasks list.

        Returns:
            Tasklist ID
        """
        if self._tasklist_id:
            return self._tasklist_id

        try:
            tasklists = self.service.tasklists().list().execute()
            for tl in tasklists.get("items", []):
                if tl.get("title") == self.TASKLIST_TITLE:
                    self._tasklist_id = tl["id"]
                    self.logger.info("tasklist_found", tasklist_id=self._tasklist_id)
                    return self._tasklist_id

            # Create new tasklist
            new_tl = self.service.tasklists().insert(body={
                "title": self.TASKLIST_TITLE
            }).execute()
            self._tasklist_id = new_tl["id"]
            self.logger.info("tasklist_created", tasklist_id=self._tasklist_id)
            return self._tasklist_id

        except HttpError as e:
            self.logger.error("tasklist_ensure_failed", error=str(e)[:100])
            raise

    async def create_task(self, task: Dict) -> str:
        """Create Google Task with shadow recurrence in notes.

        Note: Google Tasks only supports date, not time.

        Args:
            task: SmartTask dict

        Returns:
            Task ID
        """
        tasklist_id = await self.ensure_tasklist()

        try:
            # Store recurrence info in notes field
            notes = f"ai4u ID: {task.get('id', 'unknown')}"
            if task.get("recurrence"):
                notes += f"\n[RRULE:{task['recurrence']}]"

            # Add metadata
            if task.get("priority"):
                notes += f"\nPriority: {task['priority']}"
            if task.get("energy_level"):
                notes += f"\nEnergy: {task['energy_level']}"
            if task.get("context"):
                notes += f"\nContext: {task['context']}"

            task_body = {
                "title": task["content"],
                "notes": notes,
                "status": "completed" if task.get("status") == "done" else "needsAction"
            }

            # Google Tasks only supports date (no time component)
            if task.get("due_date"):
                if isinstance(task["due_date"], datetime):
                    due_date = task["due_date"].date()
                else:
                    due_date = task["due_date"]
                task_body["due"] = f"{due_date.isoformat()}T00:00:00.000Z"

            result = self.service.tasks().insert(
                tasklist=tasklist_id,
                body=task_body
            ).execute()

            self.logger.info("task_created", task_id=result["id"], ai4u_id=task.get("id"))
            return result["id"]

        except HttpError as e:
            self.logger.error("task_create_failed", error=str(e)[:100], ai4u_id=task.get("id"))
            raise

    async def update_task(self, google_task_id: str, task: Dict) -> bool:
        """Update Google Task.

        Args:
            google_task_id: Google Tasks task ID
            task: SmartTask dict with updated fields

        Returns:
            True if successful
        """
        tasklist_id = await self.ensure_tasklist()

        try:
            # Build notes with metadata
            notes = f"ai4u ID: {task.get('id', 'unknown')}"
            if task.get("recurrence"):
                notes += f"\n[RRULE:{task['recurrence']}]"
            if task.get("priority"):
                notes += f"\nPriority: {task['priority']}"

            task_body = {
                "title": task["content"],
                "notes": notes,
                "status": "completed" if task.get("status") == "done" else "needsAction"
            }

            if task.get("due_date"):
                if isinstance(task["due_date"], datetime):
                    due_date = task["due_date"].date()
                else:
                    due_date = task["due_date"]
                task_body["due"] = f"{due_date.isoformat()}T00:00:00.000Z"

            self.service.tasks().update(
                tasklist=tasklist_id,
                task=google_task_id,
                body=task_body
            ).execute()

            self.logger.info("task_updated", task_id=google_task_id, ai4u_id=task.get("id"))
            return True

        except HttpError as e:
            self.logger.error("task_update_failed", error=str(e)[:100], task_id=google_task_id)
            raise

    async def delete_task(self, google_task_id: str) -> bool:
        """Delete Google Task.

        Args:
            google_task_id: Google Tasks task ID

        Returns:
            True if deleted or already gone
        """
        tasklist_id = await self.ensure_tasklist()

        try:
            self.service.tasks().delete(
                tasklist=tasklist_id,
                task=google_task_id
            ).execute()
            self.logger.info("task_deleted", task_id=google_task_id)
            return True

        except HttpError as e:
            if e.resp.status == 404:
                self.logger.debug("task_already_deleted", task_id=google_task_id)
                return True

            self.logger.error("task_delete_failed", error=str(e)[:100], task_id=google_task_id)
            raise

    async def handle_completion(self, google_task_id: str) -> Optional[Dict]:
        """Handle task completion - create next instance if recurring.

        Args:
            google_task_id: Google Tasks task ID

        Returns:
            Next task dict if recurring, None otherwise
        """
        tasklist_id = await self.ensure_tasklist()

        try:
            task = self.service.tasks().get(
                tasklist=tasklist_id,
                task=google_task_id
            ).execute()

            # Check for recurrence in notes
            notes = task.get("notes", "")
            rrule_match = re.search(r"\[RRULE:(.+?)\]", notes)

            if not rrule_match:
                self.logger.debug("task_not_recurring", task_id=google_task_id)
                return None

            rrule_str = rrule_match.group(1)
            ai4u_id_match = re.search(r"ai4u ID: (.+)", notes)

            if not ai4u_id_match:
                self.logger.warning("task_missing_ai4u_id", task_id=google_task_id)
                return None

            ai4u_id = ai4u_id_match.group(1).strip()

            # Get next occurrence from rrule
            current_due = task.get("due")
            next_date = self._get_next_occurrence(rrule_str, current_due)

            if not next_date:
                self.logger.info("task_recurrence_ended", task_id=google_task_id, ai4u_id=ai4u_id)
                return None

            # Create next instance
            new_task_body = {
                "title": task["title"],
                "notes": notes,
                "status": "needsAction",
                "due": f"{next_date.date().isoformat()}T00:00:00.000Z"
            }

            result = self.service.tasks().insert(
                tasklist=tasklist_id,
                body=new_task_body
            ).execute()

            self.logger.info(
                "recurring_task_created",
                original_id=google_task_id,
                new_id=result["id"],
                next_date=next_date.date().isoformat()
            )

            return {
                "google_task_id": result["id"],
                "ai4u_id": ai4u_id,
                "due_date": next_date.date(),
                "recurrence": rrule_str
            }

        except HttpError as e:
            self.logger.error("completion_handling_failed", error=str(e)[:100], task_id=google_task_id)
            raise

    def _get_next_occurrence(
        self,
        rrule_str: str,
        last_due: Optional[str]
    ) -> Optional[datetime]:
        """Calculate next occurrence from RRULE.

        Args:
            rrule_str: RRULE string (without "RRULE:" prefix)
            last_due: Last due date in ISO format

        Returns:
            Next occurrence datetime or None if no more
        """
        if not last_due:
            # No previous date, use now as base
            dtstart = datetime.now(timezone.utc)
        else:
            # Parse ISO date (Google Tasks format: YYYY-MM-DDTHH:MM:SS.000Z)
            try:
                dtstart = datetime.fromisoformat(last_due.replace("Z", "+00:00"))
            except ValueError:
                self.logger.warning("invalid_due_date_format", due=last_due)
                dtstart = datetime.now(timezone.utc)

        try:
            # Security: Validate RRULE before parsing
            if not validate_rrule(rrule_str):
                self.logger.warning("invalid_rrule_rejected", rrule=rrule_str[:100])
                return None

            # Parse RRULE with dtstart
            rule = rrulestr(f"RRULE:{rrule_str}", dtstart=dtstart)

            # Get next 2 occurrences to find the one after dtstart
            next_dates = list(rule[:2])

            # Return the second occurrence (first after dtstart)
            if len(next_dates) >= 2:
                return next_dates[1]
            elif len(next_dates) == 1 and next_dates[0] > dtstart:
                return next_dates[0]
            else:
                return None

        except Exception as e:
            self.logger.error("rrule_parse_failed", rrule=rrule_str, error=str(e)[:100])
            return None

    async def list_tasks(
        self,
        show_completed: bool = False,
        updated_min: Optional[datetime] = None
    ) -> List[Dict]:
        """List tasks with optional filters.

        Args:
            show_completed: Include completed tasks
            updated_min: Only tasks updated after this datetime

        Returns:
            List of task dicts
        """
        tasklist_id = await self.ensure_tasklist()

        try:
            params = {
                "tasklist": tasklist_id,
                "showCompleted": show_completed
            }

            if updated_min:
                params["updatedMin"] = updated_min.isoformat()

            result = self.service.tasks().list(**params).execute()
            tasks = result.get("items", [])

            self.logger.info("tasks_listed", count=len(tasks))
            return tasks

        except HttpError as e:
            self.logger.error("tasks_list_failed", error=str(e)[:100])
            raise
