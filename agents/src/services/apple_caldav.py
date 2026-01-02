"""Apple iCloud CalDAV integration.

Apple CalDAV uses VEVENT (not VTODO) for better compatibility across devices.
Requires app-specific password from appleid.apple.com.
"""
from datetime import datetime, timezone, timedelta, time
from typing import Dict, List, Optional

import caldav
from caldav.elements import dav

from src.utils.logging import get_logger

logger = get_logger()


class AppleCalDAVService:
    """Apple iCloud CalDAV integration."""

    CALDAV_URL = "https://caldav.icloud.com/"
    CALENDAR_NAME = "ai4u Tasks"

    def __init__(self, apple_id: str, app_specific_password: str):
        """Initialize Apple CalDAV service.

        Args:
            apple_id: Apple ID email (e.g., user@icloud.com)
            app_specific_password: App-specific password from appleid.apple.com
        """
        self.apple_id = apple_id
        self.client = caldav.DAVClient(
            url=self.CALDAV_URL,
            username=apple_id,
            password=app_specific_password
        )
        self._principal: Optional[caldav.Principal] = None
        self._calendar: Optional[caldav.Calendar] = None
        self.logger = logger.bind(service="apple_caldav", apple_id=apple_id)

    async def connect(self) -> bool:
        """Connect and authenticate to iCloud.

        Returns:
            True if connection successful
        """
        try:
            self._principal = self.client.principal()
            self.logger.info("caldav_connected")
            return True

        except Exception as e:
            self.logger.error("caldav_connect_failed", error=str(e)[:100])
            return False

    async def ensure_calendar(self) -> Optional[caldav.Calendar]:
        """Get or create ai4u Tasks calendar.

        Returns:
            Calendar object or None if failed
        """
        if self._calendar:
            return self._calendar

        if not self._principal:
            success = await self.connect()
            if not success:
                return None

        try:
            calendars = self._principal.calendars()
            for cal in calendars:
                if cal.name == self.CALENDAR_NAME:
                    self._calendar = cal
                    self.logger.info("calendar_found", calendar_name=self.CALENDAR_NAME)
                    return self._calendar

            # Create new calendar
            self._calendar = self._principal.make_calendar(name=self.CALENDAR_NAME)
            self.logger.info("calendar_created", calendar_name=self.CALENDAR_NAME)
            return self._calendar

        except Exception as e:
            self.logger.error("calendar_ensure_failed", error=str(e)[:100])
            return None

    async def create_event(self, task: Dict) -> Optional[str]:
        """Create VEVENT in iCloud calendar.

        Note: Use VEVENT instead of VTODO for better device support.

        Args:
            task: SmartTask dict

        Returns:
            UID of created event or None if failed
        """
        calendar = await self.ensure_calendar()
        if not calendar:
            return None

        try:
            # Build datetime
            if task.get("due_date"):
                if isinstance(task["due_date"], datetime):
                    dtstart = task["due_date"]
                else:
                    dtstart = datetime.combine(
                        task["due_date"],
                        task.get("due_time") or time(9, 0)
                    )
            else:
                dtstart = datetime.now(timezone.utc) + timedelta(hours=1)

            # Ensure timezone aware
            if dtstart.tzinfo is None:
                dtstart = dtstart.replace(tzinfo=timezone.utc)

            # Calculate end time
            duration = task.get("estimated_duration", 30)
            dtend = dtstart + timedelta(minutes=duration)

            # Build UID
            uid = f"{task.get('id', 'unknown')}@ai4u"

            # Build VEVENT iCal
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//ai4u.now//Tasks//EN",
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{dtend.strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{self._escape_ical(task['content'])}",
                f"DESCRIPTION:{self._build_description(task)}",
            ]

            # Add recurrence if present
            if task.get("recurrence"):
                ical_lines.append(f"RRULE:{task['recurrence']}")

            # Add priority (1=high, 5=medium, 9=low)
            priority_map = {"p1": 1, "p2": 3, "p3": 5, "p4": 9}
            if task.get("priority"):
                ical_lines.append(f"PRIORITY:{priority_map.get(task['priority'], 5)}")

            # Add categories (tags)
            if task.get("tags"):
                tags_str = ",".join(task["tags"])
                ical_lines.append(f"CATEGORIES:{tags_str}")

            ical_lines.extend([
                "END:VEVENT",
                "END:VCALENDAR"
            ])

            ical = "\n".join(ical_lines)

            # Save event
            event = calendar.save_event(ical)
            self.logger.info("event_created", uid=uid, ai4u_id=task.get("id"))
            return uid

        except Exception as e:
            self.logger.error("event_create_failed", error=str(e)[:100], ai4u_id=task.get("id"))
            return None

    async def update_event(self, uid: str, task: Dict) -> bool:
        """Update event in iCloud calendar.

        Args:
            uid: Event UID
            task: SmartTask dict with updated fields

        Returns:
            True if successful
        """
        calendar = await self.ensure_calendar()
        if not calendar:
            return False

        try:
            # Find event by UID
            events = calendar.events()
            target_event = None

            for event in events:
                try:
                    vevent = event.vobject_instance.vevent
                    if str(vevent.uid.value) == uid:
                        target_event = event
                        break
                except Exception:
                    continue

            if not target_event:
                self.logger.warning("event_not_found", uid=uid)
                return False

            # Delete old event and create new one (CalDAV update can be tricky)
            target_event.delete()
            new_uid = await self.create_event(task)

            self.logger.info("event_updated", old_uid=uid, new_uid=new_uid)
            return new_uid is not None

        except Exception as e:
            self.logger.error("event_update_failed", error=str(e)[:100], uid=uid)
            return False

    async def delete_event(self, uid: str) -> bool:
        """Delete event from iCloud calendar.

        Args:
            uid: Event UID

        Returns:
            True if deleted or not found
        """
        calendar = await self.ensure_calendar()
        if not calendar:
            return False

        try:
            # Find event by UID
            events = calendar.events()
            target_event = None

            for event in events:
                try:
                    vevent = event.vobject_instance.vevent
                    if str(vevent.uid.value) == uid:
                        target_event = event
                        break
                except Exception:
                    continue

            if not target_event:
                self.logger.debug("event_already_deleted", uid=uid)
                return True

            target_event.delete()
            self.logger.info("event_deleted", uid=uid)
            return True

        except Exception as e:
            self.logger.error("event_delete_failed", error=str(e)[:100], uid=uid)
            return False

    async def sync_changes(self, since: Optional[datetime] = None) -> List[Dict]:
        """Fetch changes from iCloud calendar.

        Note: CalDAV doesn't have sync tokens like Google Calendar,
        so we use time-based filtering.

        Args:
            since: Only events modified after this time (default: last 24h)

        Returns:
            List of changed event dicts
        """
        calendar = await self.ensure_calendar()
        if not calendar:
            return []

        if not since:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        try:
            # Get events modified in date range
            end_date = datetime.now(timezone.utc) + timedelta(days=365)
            events = calendar.date_search(start=since, end=end_date)

            changes = []
            for event in events:
                try:
                    vevent = event.vobject_instance.vevent

                    # Extract event data
                    event_dict = {
                        "uid": str(vevent.uid.value),
                        "summary": str(vevent.summary.value) if hasattr(vevent, "summary") else "",
                        "start": vevent.dtstart.value if hasattr(vevent, "dtstart") else None,
                        "end": vevent.dtend.value if hasattr(vevent, "dtend") else None,
                        "etag": event.get_property("etag") or "",
                    }

                    # Extract recurrence if present
                    if hasattr(vevent, "rrule"):
                        event_dict["recurrence"] = str(vevent.rrule.value)

                    changes.append(event_dict)

                except Exception as e:
                    self.logger.debug("event_parse_failed", error=str(e)[:50])
                    continue

            self.logger.info("sync_completed", changes_count=len(changes))
            return changes

        except Exception as e:
            self.logger.error("sync_changes_failed", error=str(e)[:100])
            return []

    def _escape_ical(self, text: str) -> str:
        """Escape special characters for iCal format.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        return (text
                .replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\n", "\\n"))

    def _build_description(self, task: Dict) -> str:
        """Build event description from task metadata.

        Args:
            task: SmartTask dict

        Returns:
            Escaped description string
        """
        lines = [f"ai4u ID: {task.get('id', 'unknown')}"]

        if task.get("priority"):
            lines.append(f"Priority: {task['priority']}")

        if task.get("energy_level"):
            lines.append(f"Energy: {task['energy_level']}")

        if task.get("context"):
            lines.append(f"Context: {task['context']}")

        if task.get("project"):
            lines.append(f"Project: {task['project']}")

        desc = "\\n".join(lines)
        return self._escape_ical(desc)
