
import pytest
from datetime import datetime, timedelta, timezone, date, time
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add agents directory to path
sys.path.insert(0, os.path.abspath('agents'))

# Mock caldav before importing anything that might use it
sys.modules['caldav'] = MagicMock()
sys.modules['caldav.elements'] = MagicMock()

from src.core.calendar_sync import CalendarSyncManager, SyncResult
from src.services.google_tasks import GoogleTasksService
from src.services.google_calendar import GoogleCalendarService

@pytest.mark.asyncio
async def test_calendar_sync_manager_no_creds():
    manager = CalendarSyncManager()
    task = {"id": "task-1", "content": "Test"}
    user_settings = {"google_calendar_enabled": True}
    credentials = {} # Missing creds

    result = await manager.sync_task(task, user_settings, credentials)
    assert result.google_calendar is False
    assert "google_calendar: missing credentials" in result.errors

@pytest.mark.asyncio
async def test_google_tasks_service_next_occurrence():
    mock_creds = MagicMock()
    with patch("src.services.google_tasks.build"):
        service = GoogleTasksService(mock_creds)

        rrule = "FREQ=DAILY"
        last_due = "2026-01-01T00:00:00.000Z"

        next_date = service._get_next_occurrence(rrule, last_due)
        assert next_date.date() == date(2026, 1, 2)

@pytest.mark.asyncio
async def test_google_calendar_service_build_datetime():
    mock_creds = MagicMock()
    with patch("src.services.google_calendar.build"):
        service = GoogleCalendarService(mock_creds)

        target_date = date(2026, 1, 2)
        target_time = time(10, 0)

        dt_obj = service._build_datetime(target_date, target_time)
        assert "dateTime" in dt_obj
        assert "2026-01-02T10:00:00" in dt_obj["dateTime"]
