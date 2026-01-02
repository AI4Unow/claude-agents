"""Google Calendar API wrapper with sync token support.

Bidirectional sync with Google Calendar using OAuth2, ETags, and incremental sync.
"""
import html
import re
from datetime import datetime, timezone, timedelta, time
from typing import Dict, List, Optional, Tuple

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils.logging import get_logger

logger = get_logger()


# Security: Limits for calendar description fields
MAX_TASK_ID_LENGTH = 100
MAX_PRIORITY_LENGTH = 10
MAX_ENERGY_LENGTH = 20
MAX_CONTEXT_LENGTH = 50
MAX_TAG_LENGTH = 50
MAX_TAG_COUNT = 10
MAX_PROJECT_LENGTH = 100


class GoogleCalendarService:
    """Google Calendar API wrapper with sync token support."""

    SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
    CALENDAR_NAME = "ai4u Tasks"

    def __init__(self, credentials: Credentials):
        """Initialize Google Calendar service.

        Args:
            credentials: OAuth2 credentials from Google
        """
        self.service = build("calendar", "v3", credentials=credentials)
        self._calendar_id: Optional[str] = None
        self.logger = logger.bind(service="google_calendar")

    async def ensure_calendar(self) -> str:
        """Get or create ai4u Tasks calendar.

        Returns:
            Calendar ID
        """
        if self._calendar_id:
            return self._calendar_id

        try:
            # List calendars
            calendars = self.service.calendarList().list().execute()
            for cal in calendars.get("items", []):
                if cal.get("summary") == self.CALENDAR_NAME:
                    self._calendar_id = cal["id"]
                    self.logger.info("calendar_found", calendar_id=self._calendar_id)
                    return self._calendar_id

            # Create if not exists
            new_cal = self.service.calendars().insert(body={
                "summary": self.CALENDAR_NAME,
                "description": "Tasks managed by ai4u.now"
            }).execute()
            self._calendar_id = new_cal["id"]
            self.logger.info("calendar_created", calendar_id=self._calendar_id)
            return self._calendar_id

        except HttpError as e:
            self.logger.error("calendar_ensure_failed", error=str(e)[:100])
            raise

    async def create_event(self, task: Dict) -> str:
        """Create calendar event from task.

        Args:
            task: SmartTask dict with due_date, due_time, content, etc.

        Returns:
            Event ID
        """
        calendar_id = await self.ensure_calendar()

        try:
            event_body = {
                "summary": task["content"],
                "description": self._build_description(task),
                "start": self._build_datetime(
                    task.get("due_date"),
                    task.get("due_time")
                ),
                "end": self._build_datetime(
                    task.get("due_date"),
                    task.get("due_time"),
                    duration_minutes=task.get("estimated_duration", 30)
                ),
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": task.get("reminder_offset", 15)}
                    ]
                }
            }

            # Add recurrence if present
            if task.get("recurrence"):
                event_body["recurrence"] = [f"RRULE:{task['recurrence']}"]

            result = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()

            self.logger.info("event_created", event_id=result["id"], task_id=task.get("id"))
            return result["id"]

        except HttpError as e:
            self.logger.error("event_create_failed", error=str(e)[:100], task_id=task.get("id"))
            raise

    async def update_event(
        self,
        event_id: str,
        task: Dict,
        etag: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Update event with ETag check for optimistic concurrency.

        Args:
            event_id: Google Calendar event ID
            task: SmartTask dict with updated fields
            etag: Last known ETag (for conflict detection)

        Returns:
            Tuple of (success, new_etag)
        """
        calendar_id = await self.ensure_calendar()

        try:
            event_body = {
                "summary": task["content"],
                "description": self._build_description(task),
                "start": self._build_datetime(
                    task.get("due_date"),
                    task.get("due_time")
                ),
                "end": self._build_datetime(
                    task.get("due_date"),
                    task.get("due_time"),
                    duration_minutes=task.get("estimated_duration", 30)
                ),
            }

            # Add recurrence if present
            if task.get("recurrence"):
                event_body["recurrence"] = [f"RRULE:{task['recurrence']}"]

            # Add ETag header if provided
            headers = {}
            if etag:
                headers["If-Match"] = etag

            result = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_body,
                **({"headers": headers} if headers else {})
            ).execute()

            self.logger.info("event_updated", event_id=event_id, task_id=task.get("id"))
            return True, result.get("etag")

        except HttpError as e:
            if e.resp.status == 412:  # Precondition failed (ETag mismatch)
                self.logger.warning("event_update_conflict", event_id=event_id, task_id=task.get("id"))
                return False, None

            self.logger.error("event_update_failed", error=str(e)[:100], event_id=event_id)
            raise

    async def delete_event(self, event_id: str) -> bool:
        """Delete event from calendar.

        Args:
            event_id: Google Calendar event ID

        Returns:
            True if deleted or already gone
        """
        calendar_id = await self.ensure_calendar()

        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            self.logger.info("event_deleted", event_id=event_id)
            return True

        except HttpError as e:
            if e.resp.status == 404:
                self.logger.debug("event_already_deleted", event_id=event_id)
                return True  # Already deleted

            self.logger.error("event_delete_failed", error=str(e)[:100], event_id=event_id)
            raise

    async def incremental_sync(
        self,
        sync_token: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """Perform incremental sync using sync tokens.

        Args:
            sync_token: Last sync token (None for initial full sync)

        Returns:
            Tuple of (changed_events, new_sync_token)
        """
        calendar_id = await self.ensure_calendar()

        params = {"calendarId": calendar_id}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            # Initial full sync - only future events
            params["timeMin"] = datetime.now(timezone.utc).isoformat()

        try:
            result = self.service.events().list(**params).execute()
            events = result.get("items", [])
            new_token = result.get("nextSyncToken")

            self.logger.info(
                "incremental_sync_completed",
                events_count=len(events),
                has_token=bool(new_token)
            )
            return events, new_token

        except HttpError as e:
            if e.resp.status == 410:  # Sync token expired
                self.logger.warning("sync_token_expired", retrying=True)
                return await self.incremental_sync(sync_token=None)

            self.logger.error("incremental_sync_failed", error=str(e)[:100])
            raise

    async def setup_webhook(self, webhook_url: str, channel_id: str) -> Dict:
        """Set up push notifications for calendar changes.

        Args:
            webhook_url: HTTPS URL to receive webhook notifications
            channel_id: Unique channel identifier

        Returns:
            Channel info dict
        """
        calendar_id = await self.ensure_calendar()

        try:
            # Webhook expires after 7 days, needs renewal
            expiration = int((datetime.now() + timedelta(days=7)).timestamp() * 1000)

            channel = self.service.events().watch(
                calendarId=calendar_id,
                body={
                    "id": channel_id,
                    "type": "web_hook",
                    "address": webhook_url,
                    "expiration": expiration
                }
            ).execute()

            self.logger.info(
                "webhook_setup",
                channel_id=channel_id,
                expires=datetime.fromtimestamp(expiration / 1000, tz=timezone.utc).isoformat()
            )
            return channel

        except HttpError as e:
            self.logger.error("webhook_setup_failed", error=str(e)[:100])
            raise

    def _build_datetime(
        self,
        date: Optional[datetime],
        time_val: Optional[time] = None,
        duration_minutes: int = 0
    ) -> Dict:
        """Build Google Calendar datetime object.

        Args:
            date: Date (datetime or date object)
            time_val: Optional time component
            duration_minutes: Minutes to add (for end time)

        Returns:
            Dict with 'dateTime' or 'date' field
        """
        if not date:
            # Default to now + 1 hour
            dt = datetime.now(timezone.utc) + timedelta(hours=1)
        else:
            # Convert date to datetime
            if isinstance(date, datetime):
                dt = date
            else:
                dt = datetime.combine(date, time_val or time(9, 0))

            # Ensure timezone aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

        # Add duration for end time
        if duration_minutes > 0:
            dt = dt + timedelta(minutes=duration_minutes)

        # If time component exists, use dateTime; otherwise use date
        if time_val or isinstance(date, datetime):
            return {"dateTime": dt.isoformat()}
        else:
            return {"date": dt.date().isoformat()}

    def _build_description(self, task: Dict) -> str:
        """Build event description from task metadata.

        Security: All user inputs are HTML-escaped and length-limited to prevent
        iCal injection and XSS attacks.

        Args:
            task: SmartTask dict

        Returns:
            Formatted description string
        """
        # Sanitize task ID
        task_id = html.escape(str(task.get('id', 'unknown'))[:MAX_TASK_ID_LENGTH])
        lines = [f"Task ID: {task_id}"]

        if task.get("priority"):
            priority = html.escape(str(task['priority'])[:MAX_PRIORITY_LENGTH])
            lines.append(f"Priority: {priority}")

        if task.get("energy_level"):
            energy = html.escape(str(task['energy_level'])[:MAX_ENERGY_LENGTH])
            lines.append(f"Energy: {energy}")

        if task.get("context"):
            context = html.escape(str(task['context'])[:MAX_CONTEXT_LENGTH])
            lines.append(f"Context: {context}")

        if task.get("tags"):
            # Limit tag count and sanitize each tag
            safe_tags = [
                html.escape(str(tag)[:MAX_TAG_LENGTH])
                for tag in task['tags'][:MAX_TAG_COUNT]
            ]
            lines.append(f"Tags: {', '.join(safe_tags)}")

        if task.get("project"):
            project = html.escape(str(task['project'])[:MAX_PROJECT_LENGTH])
            lines.append(f"Project: {project}")

        return "\n".join(lines)
