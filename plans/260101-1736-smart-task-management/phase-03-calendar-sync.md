# Phase 3: Calendar Sync

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: [Phase 1](phase-01-core-foundation.md), [Phase 2](phase-02-smart-features.md)
- **Research**: [Calendar APIs](research/researcher-calendar-apis.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2026-01-01 |
| Priority | P1 |
| Effort | 8h |
| Status | pending |

Bidirectional sync with Google Calendar, Google Tasks, and Apple CalDAV. Firebase remains source of truth.

## Key Insights (from Research)

1. **Google Calendar**: OAuth2 + sync tokens + ETags + webhooks
2. **Google Tasks**: No recurrence API - use shadow system with `dateutil.rrule`
3. **Apple CalDAV**: App-specific passwords required, limited VTODO support
4. **Conflict resolution**: ETags for optimistic concurrency, last-write-wins

## Requirements

1. OAuth2 flow for Google Calendar/Tasks
2. Create dedicated "ai4u Tasks" calendar in Google
3. Sync SmartTasks ↔ Google Calendar events (time-blocked)
4. Sync SmartTasks ↔ Google Tasks (date-only, no recurrence)
5. Apple CalDAV integration with app-specific passwords
6. Conflict resolution with ETags, Firebase as truth
7. Sync status visible to users

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PHASE 3 ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SmartTask (Firebase - Source of Truth)                                  │
│       │                                                                  │
│       │  Sync Manager                                                    │
│       │  ┌─────────────────────────────────────────────────────────┐    │
│       └──►│                                                         │    │
│          │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │    │
│          │  │   Google    │  │   Google    │  │    Apple    │     │    │
│          │  │  Calendar   │  │   Tasks     │  │   CalDAV    │     │    │
│          │  │  Service    │  │  Service    │  │  Service    │     │    │
│          │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │    │
│          │         │                │                │             │    │
│          │  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐     │    │
│          │  │ OAuth2 +    │  │ OAuth2 +    │  │ App-Specific│     │    │
│          │  │ Sync Tokens │  │ Shadow Rec. │  │ Password    │     │    │
│          │  │ + ETags     │  │ + ETags     │  │ + caldav    │     │    │
│          │  └─────────────┘  └─────────────┘  └─────────────┘     │    │
│          │                                                         │    │
│          │  Conflict Resolution: ETag mismatch → Firebase wins     │    │
│          └─────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Webhook: /webhook/google-calendar → Incremental sync                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Files

| File | Action | Purpose |
|------|--------|---------|
| `src/services/google_calendar.py` | Create | Google Calendar API wrapper |
| `src/services/google_tasks.py` | Create | Google Tasks API wrapper |
| `src/services/apple_caldav.py` | Create | Apple CalDAV wrapper |
| `src/core/calendar_sync.py` | Create | Sync orchestration |
| `src/services/firebase/calendar_tokens.py` | Create | Store OAuth tokens |
| `api/routes/google_auth.py` | Create | OAuth2 callback endpoint |
| `main.py` | Modify | Add webhook endpoint |

## Implementation Steps

### 1. Google Calendar Integration (3h)

1.1. Create `src/services/google_calendar.py`:
```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleCalendarService:
    """Google Calendar API wrapper with sync token support."""

    SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
    CALENDAR_NAME = "ai4u Tasks"

    def __init__(self, credentials: Credentials):
        self.service = build("calendar", "v3", credentials=credentials)
        self._calendar_id = None

    async def ensure_calendar(self) -> str:
        """Get or create ai4u Tasks calendar."""
        if self._calendar_id:
            return self._calendar_id

        # List calendars
        calendars = self.service.calendarList().list().execute()
        for cal in calendars.get("items", []):
            if cal.get("summary") == self.CALENDAR_NAME:
                self._calendar_id = cal["id"]
                return self._calendar_id

        # Create if not exists
        new_cal = self.service.calendars().insert(body={
            "summary": self.CALENDAR_NAME,
            "description": "Tasks managed by ai4u.now"
        }).execute()
        self._calendar_id = new_cal["id"]
        return self._calendar_id

    async def create_event(self, task: SmartTask) -> str:
        """Create calendar event from task. Returns event ID."""
        calendar_id = await self.ensure_calendar()

        event_body = {
            "summary": task.content,
            "description": f"Task ID: {task.id}\nPriority: {task.priority or 'none'}",
            "start": self._build_datetime(task.due_date, task.due_time),
            "end": self._build_datetime(
                task.due_date,
                task.due_time,
                duration_minutes=task.estimated_duration or 30
            ),
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": task.reminder_offset or 15}
                ]
            }
        }

        if task.recurrence:
            event_body["recurrence"] = [f"RRULE:{task.recurrence}"]

        result = self.service.events().insert(
            calendarId=calendar_id,
            body=event_body
        ).execute()

        return result["id"]

    async def update_event(
        self,
        event_id: str,
        task: SmartTask,
        etag: str
    ) -> Tuple[bool, Optional[str]]:
        """Update event with ETag check. Returns (success, new_etag)."""
        calendar_id = await self.ensure_calendar()

        try:
            event_body = {
                "summary": task.content,
                "start": self._build_datetime(task.due_date, task.due_time),
                "end": self._build_datetime(
                    task.due_date, task.due_time,
                    duration_minutes=task.estimated_duration or 30
                ),
            }

            result = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_body,
                headers={"If-Match": etag}
            ).execute()

            return True, result.get("etag")

        except HttpError as e:
            if e.resp.status == 412:  # Precondition failed
                return False, None
            raise

    async def delete_event(self, event_id: str) -> bool:
        """Delete event from calendar."""
        calendar_id = await self.ensure_calendar()
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True
        except HttpError as e:
            if e.resp.status == 404:
                return True  # Already deleted
            raise

    async def incremental_sync(
        self,
        sync_token: Optional[str] = None
    ) -> Tuple[List[Dict], str]:
        """Perform incremental sync. Returns (changed_events, new_sync_token)."""
        calendar_id = await self.ensure_calendar()

        params = {"calendarId": calendar_id}
        if sync_token:
            params["syncToken"] = sync_token
        else:
            # Initial full sync
            params["timeMin"] = datetime.now(timezone.utc).isoformat()

        try:
            result = self.service.events().list(**params).execute()
            events = result.get("items", [])
            new_token = result.get("nextSyncToken")
            return events, new_token

        except HttpError as e:
            if e.resp.status == 410:  # Sync token expired
                return await self.incremental_sync(sync_token=None)
            raise

    async def setup_webhook(self, webhook_url: str, channel_id: str) -> Dict:
        """Set up push notifications for calendar changes."""
        calendar_id = await self.ensure_calendar()

        channel = self.service.events().watch(
            calendarId=calendar_id,
            body={
                "id": channel_id,
                "type": "web_hook",
                "address": webhook_url,
                "expiration": int((datetime.now() + timedelta(days=7)).timestamp() * 1000)
            }
        ).execute()

        return channel
```

1.2. OAuth2 flow endpoint:
```python
# api/routes/google_auth.py
@router.get("/auth/google/callback")
async def google_callback(code: str, state: str):
    """Handle OAuth2 callback from Google."""
    # Verify state matches user session
    user_id = verify_state(state)

    # Exchange code for tokens
    flow = google_auth_oauthlib.flow.Flow.from_client_config(...)
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Store tokens in Firebase
    await store_google_tokens(
        user_id=user_id,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        expiry=credentials.expiry
    )

    return RedirectResponse("/auth/success")
```

### 2. Google Tasks Integration (2h)

2.1. Create `src/services/google_tasks.py`:
```python
class GoogleTasksService:
    """Google Tasks API with shadow recurrence system."""

    SCOPES = ["https://www.googleapis.com/auth/tasks"]
    TASKLIST_TITLE = "ai4u Tasks"

    def __init__(self, credentials: Credentials):
        self.service = build("tasks", "v1", credentials=credentials)
        self._tasklist_id = None

    async def ensure_tasklist(self) -> str:
        """Get or create ai4u Tasks list."""
        if self._tasklist_id:
            return self._tasklist_id

        tasklists = self.service.tasklists().list().execute()
        for tl in tasklists.get("items", []):
            if tl.get("title") == self.TASKLIST_TITLE:
                self._tasklist_id = tl["id"]
                return self._tasklist_id

        new_tl = self.service.tasklists().insert(body={
            "title": self.TASKLIST_TITLE
        }).execute()
        self._tasklist_id = new_tl["id"]
        return self._tasklist_id

    async def create_task(self, task: SmartTask) -> str:
        """Create Google Task. Note: only date, no time support."""
        tasklist_id = await self.ensure_tasklist()

        # Store recurrence info in notes field
        notes = f"ai4u ID: {task.id}"
        if task.recurrence:
            notes += f"\n[RRULE:{task.recurrence}]"

        task_body = {
            "title": task.content,
            "notes": notes,
            "status": "needsAction" if task.status != "done" else "completed"
        }

        if task.due_date:
            # Google Tasks only supports date, not time
            task_body["due"] = task.due_date.strftime("%Y-%m-%dT00:00:00.000Z")

        result = self.service.tasks().insert(
            tasklist=tasklist_id,
            body=task_body
        ).execute()

        return result["id"]

    async def handle_completion(self, google_task_id: str) -> Optional[SmartTask]:
        """Handle task completion - create next instance if recurring."""
        tasklist_id = await self.ensure_tasklist()

        task = self.service.tasks().get(
            tasklist=tasklist_id,
            task=google_task_id
        ).execute()

        # Check for recurrence in notes
        notes = task.get("notes", "")
        rrule_match = re.search(r"\[RRULE:(.+)\]", notes)

        if rrule_match:
            rrule_str = rrule_match.group(1)
            ai4u_id = re.search(r"ai4u ID: (.+)", notes)

            if ai4u_id:
                # Get next occurrence from rrule
                next_date = self._get_next_occurrence(rrule_str, task.get("due"))

                if next_date:
                    # Create next instance
                    new_task = await self._clone_task(task, next_date)
                    return new_task

        return None

    def _get_next_occurrence(
        self,
        rrule_str: str,
        last_date: str
    ) -> Optional[datetime]:
        """Calculate next occurrence from RRULE."""
        from dateutil.rrule import rrulestr

        if not last_date:
            return None

        rule = rrulestr(f"RRULE:{rrule_str}", dtstart=datetime.fromisoformat(last_date.replace("Z", "+00:00")))
        next_dates = list(rule[:2])

        if len(next_dates) >= 2:
            return next_dates[1]
        return None
```

### 3. Apple CalDAV Integration (2h)

3.1. Create `src/services/apple_caldav.py`:
```python
import caldav
from caldav.elements import dav, cdav

class AppleCalDAVService:
    """Apple iCloud CalDAV integration."""

    CALDAV_URL = "https://caldav.icloud.com/"
    CALENDAR_NAME = "ai4u Tasks"

    def __init__(self, apple_id: str, app_specific_password: str):
        self.client = caldav.DAVClient(
            url=self.CALDAV_URL,
            username=apple_id,
            password=app_specific_password
        )
        self._principal = None
        self._calendar = None

    async def connect(self) -> bool:
        """Connect and authenticate to iCloud."""
        try:
            self._principal = self.client.principal()
            return True
        except Exception as e:
            logger.error("apple_caldav_connect_failed", error=str(e))
            return False

    async def ensure_calendar(self) -> Optional[caldav.Calendar]:
        """Get or create ai4u Tasks calendar."""
        if self._calendar:
            return self._calendar

        if not self._principal:
            await self.connect()

        calendars = self._principal.calendars()
        for cal in calendars:
            if cal.name == self.CALENDAR_NAME:
                self._calendar = cal
                return self._calendar

        # Create new calendar
        try:
            self._calendar = self._principal.make_calendar(name=self.CALENDAR_NAME)
            return self._calendar
        except Exception as e:
            logger.error("apple_caldav_create_calendar_failed", error=str(e))
            return None

    async def create_event(self, task: SmartTask) -> Optional[str]:
        """Create VEVENT in iCloud calendar. Returns UID."""
        calendar = await self.ensure_calendar()
        if not calendar:
            return None

        # Build VEVENT
        dtstart = datetime.combine(task.due_date, task.due_time or time(9, 0))
        dtend = dtstart + timedelta(minutes=task.estimated_duration or 30)

        ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ai4u.now//Tasks//EN
BEGIN:VEVENT
UID:{task.id}@ai4u
DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{dtstart.strftime('%Y%m%dT%H%M%S')}
DTEND:{dtend.strftime('%Y%m%dT%H%M%S')}
SUMMARY:{task.content}
DESCRIPTION:Priority: {task.priority or 'none'}
"""
        if task.recurrence:
            ical += f"RRULE:{task.recurrence}\n"

        ical += """END:VEVENT
END:VCALENDAR"""

        try:
            event = calendar.save_event(ical)
            return task.id
        except Exception as e:
            logger.error("apple_caldav_create_event_failed", error=str(e))
            return None

    async def sync_changes(self) -> List[Dict]:
        """Fetch changes from iCloud calendar."""
        calendar = await self.ensure_calendar()
        if not calendar:
            return []

        # Get events modified in last 24h
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        events = calendar.date_search(
            start=since,
            end=datetime.now(timezone.utc) + timedelta(days=365)
        )

        changes = []
        for event in events:
            try:
                vevent = event.vobject_instance.vevent
                changes.append({
                    "uid": str(vevent.uid.value),
                    "summary": str(vevent.summary.value),
                    "start": vevent.dtstart.value,
                    "end": vevent.dtend.value if hasattr(vevent, 'dtend') else None,
                    "etag": event.get_property("etag")
                })
            except Exception:
                continue

        return changes
```

### 4. Sync Manager (1h)

4.1. Create `src/core/calendar_sync.py`:
```python
@dataclass
class SyncStatus:
    user_id: int
    google_calendar: Literal["connected", "disconnected", "error"]
    google_tasks: Literal["connected", "disconnected", "error"]
    apple_caldav: Literal["connected", "disconnected", "error"]
    last_sync: Optional[datetime]
    pending_conflicts: int

class CalendarSyncManager:
    """Orchestrate sync across all calendar services."""

    async def sync_task(
        self,
        task: SmartTask,
        user_settings: Dict
    ) -> Dict[str, bool]:
        """Sync task to enabled calendar services."""
        results = {}

        # Google Calendar
        if user_settings.get("google_calendar_enabled"):
            try:
                creds = await get_google_credentials(task.user_id)
                gcal = GoogleCalendarService(creds)

                if task.google_event_id:
                    # Update existing
                    etag = await get_event_etag(task.user_id, task.google_event_id)
                    success, new_etag = await gcal.update_event(
                        task.google_event_id, task, etag
                    )
                    if success:
                        await store_event_etag(task.user_id, task.google_event_id, new_etag)
                    results["google_calendar"] = success
                else:
                    # Create new
                    event_id = await gcal.create_event(task)
                    await update_task(task.user_id, task.id, google_event_id=event_id)
                    results["google_calendar"] = True

            except Exception as e:
                logger.error("google_calendar_sync_failed", error=str(e))
                results["google_calendar"] = False

        # Google Tasks
        if user_settings.get("google_tasks_enabled"):
            try:
                creds = await get_google_credentials(task.user_id)
                gtasks = GoogleTasksService(creds)

                if task.google_task_id:
                    await gtasks.update_task(task.google_task_id, task)
                else:
                    task_id = await gtasks.create_task(task)
                    await update_task(task.user_id, task.id, google_task_id=task_id)
                results["google_tasks"] = True

            except Exception as e:
                logger.error("google_tasks_sync_failed", error=str(e))
                results["google_tasks"] = False

        # Apple CalDAV
        if user_settings.get("apple_caldav_enabled"):
            try:
                apple_creds = await get_apple_credentials(task.user_id)
                apple = AppleCalDAVService(
                    apple_creds["apple_id"],
                    apple_creds["app_password"]
                )

                if task.apple_uid:
                    await apple.update_event(task)
                else:
                    uid = await apple.create_event(task)
                    await update_task(task.user_id, task.id, apple_uid=uid)
                results["apple_caldav"] = True

            except Exception as e:
                logger.error("apple_caldav_sync_failed", error=str(e))
                results["apple_caldav"] = False

        return results

    async def handle_external_change(
        self,
        source: str,
        event_data: Dict,
        user_id: int
    ) -> None:
        """Handle change from external calendar. Firebase wins conflicts."""

        # Find matching SmartTask
        task = await find_task_by_external_id(source, event_data["id"], user_id)

        if not task:
            # Event created externally - ignore or import based on settings
            return

        # Compare timestamps
        external_updated = event_data.get("updated")
        if task.updated_at and external_updated:
            if task.updated_at > external_updated:
                # Firebase is newer - push back to external
                await self.sync_task(task, await get_user_settings(user_id))
            else:
                # External is newer - update Firebase
                await update_task(
                    user_id, task.id,
                    due_date=event_data.get("start"),
                    content=event_data.get("summary")
                )

    async def get_sync_status(self, user_id: int) -> SyncStatus:
        """Get current sync status for user."""
        settings = await get_user_settings(user_id)
        conflicts = await count_pending_conflicts(user_id)

        return SyncStatus(
            user_id=user_id,
            google_calendar="connected" if settings.get("google_calendar_enabled") else "disconnected",
            google_tasks="connected" if settings.get("google_tasks_enabled") else "disconnected",
            apple_caldav="connected" if settings.get("apple_caldav_enabled") else "disconnected",
            last_sync=settings.get("last_sync"),
            pending_conflicts=conflicts
        )
```

## Todo List

- [ ] Set up Google Cloud project with Calendar + Tasks API
- [ ] Create Google OAuth2 flow endpoints
- [ ] Build GoogleCalendarService with sync tokens
- [ ] Implement ETag-based conflict resolution
- [ ] Set up Google Calendar webhook
- [ ] Build GoogleTasksService with shadow recurrence
- [ ] Create AppleCalDAVService wrapper
- [ ] Implement CalendarSyncManager orchestration
- [ ] Store OAuth tokens securely in Firebase
- [ ] Add sync status to user settings
- [ ] Create circuit breaker for each calendar service
- [ ] Write integration tests with mocked APIs

## Success Criteria

1. Google Calendar OAuth flow completes in < 30 seconds
2. Task → Calendar event sync in < 5 seconds
3. ETag conflicts detected 100% of time
4. Shadow recurrence creates next instance correctly
5. Apple CalDAV connects with app-specific password

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| OAuth token expiry | High | High | Auto-refresh, error handling |
| Google API quota limits | Medium | Medium | Exponential backoff, caching |
| Apple CalDAV VTODO stripped | Medium | High | Use VEVENT instead of VTODO |
| Webhook delivery failures | Medium | Low | Fallback polling every 15 min |
| Credential storage security | High | Low | Encrypt at rest, audit logs |

## Security Considerations

1. OAuth tokens encrypted in Firebase with user-specific keys
2. App-specific passwords never logged
3. Webhook endpoints validate X-Goog-Resource-ID header
4. Rate limit OAuth callback endpoint
5. Token refresh in background, not on user request path

## Next Steps

After Phase 3 complete:
1. Proceed to [Phase 4: Web Dashboard](phase-04-web-dashboard.md)
2. Test sync with real Google/Apple accounts
3. Monitor API quota usage

## Unresolved Questions

1. Should we support importing external calendar events as tasks?
2. How to handle multi-calendar scenarios (work vs personal)?
3. What's the polling interval for Apple CalDAV (no webhooks)?
4. Should OAuth tokens be refreshed proactively or lazily?
