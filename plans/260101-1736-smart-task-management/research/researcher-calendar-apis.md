# Calendar API Integration Research Report

## 1. Google Calendar API
- **Auth**: OAuth2 flow (code exchange for `access_token` and `refresh_token`). Scopes: `.../auth/calendar` or `.../auth/calendar.events`.
- **Sync Pattern**:
    1. **Initial Sync**: `events().list()` -> returns `nextSyncToken`.
    2. **Incremental Sync**: `events().list(syncToken=...)` -> returns only changed/deleted events.
- **Webhooks**: `events().watch()` subscription. Requires HTTPS endpoint. Notifies of change; client then performs incremental sync.
- **Conflict Resolution**: Uses **ETags**. Update requests must include `If-Match: <etag>`. Failure returns `412 Precondition Failed`.

## 2. Google Tasks API
- **Limitations**:
    - **No Native Recurrence**: Recurrence rules are not visible or settable via API.
    - **Single Instance**: Only the current active instance of a recurring task (created in UI) is visible.
- **Workarounds**:
    - **Shadow System**: Maintain recurrence rules in local DB. Python script (using `dateutil.rrule`) creates next instance upon completion of current.
    - **Notes Metadata**: Store JSON/tags in `notes` field (e.g., `[REPEAT:WEEKLY]`).
    - **Hybrid Strategy**: Use Google Calendar for "Time-blocked" tasks to leverage native RRULE support.

## 3. Apple CalDAV (iCloud)
- **Auth**: Mandatory **App-Specific Passwords**. Does NOT support OAuth2 for CalDAV. Requires 2FA enabled.
- **Library**: `caldav` (Python). Handles `pXX-caldav.icloud.com` cluster redirection automatically via base URL `https://caldav.icloud.com/`.
- **Limitations**:
    - `VTODO` support is often ignored/stripped by iCloud CalDAV server.
    - No native free/busy or calendar creation via API.
    - Recurring event support can be brittle.

## 4. Conflict Resolution Strategies
- **Optimistic (ETags)**: Preferred for API-based sync. Check version before write.
- **Last-Write-Wins (LWW)**: Fallback for offline sync. Risk of data loss due to clock skew or "lost updates".
- **Semantic Merging**: Field-level diffing (e.g., merging description change with location change). High complexity.

## Unresolved Questions
1. Does iCloud's specific CalDAV implementation support sync tokens or similar incremental mechanisms beyond ETag-based polling?
2. What is the exact behavior of Google Tasks when a "recurring" task is deleted vs. marked completed via API?
3. Are there rate limit differences between `watch()` notifications and high-frequency polling for CalDAV?
