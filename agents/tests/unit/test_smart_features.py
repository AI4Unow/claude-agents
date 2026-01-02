
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add agents directory to path
sys.path.insert(0, os.path.abspath('agents'))

from src.core.smart_timing import SmartTimingEngine
from src.core.task_extractor import TaskExtractor
from src.core.auto_scheduler import AutoScheduler
from src.core.completion_verifier import CompletionVerifier
from src.services.firebase.pkm import SmartTask

@pytest.fixture
def timing_engine():
    return SmartTimingEngine()

@pytest.fixture
def task_extractor():
    return TaskExtractor()

@pytest.fixture
def auto_scheduler():
    return AutoScheduler()

@pytest.fixture
def completion_verifier():
    return CompletionVerifier()

def test_timing_priority_weight(timing_engine):
    assert timing_engine._priority_weight("p1") == 1.0
    assert timing_engine._priority_weight("p4") == 0.25
    assert timing_engine._priority_weight(None) == 0.5

def test_timing_gap_score(timing_engine):
    target = datetime(2026, 1, 2, 12, 0, 0)
    events = [
        {"start": datetime(2026, 1, 2, 9, 0, 0), "end": datetime(2026, 1, 2, 10, 0, 0)},
        {"start": datetime(2026, 1, 2, 11, 0, 0), "end": datetime(2026, 1, 2, 11, 30, 0)}
    ]
    # Gap between 10:00 and 11:00 is 60 mins -> score 1.0
    score = timing_engine._find_gap_score(events, target)
    assert score == 1.0

def test_task_extractor_patterns(task_extractor):
    msg = "I need to buy milk tomorrow"
    matches = task_extractor._pattern_extract(msg)
    assert len(matches) > 0
    assert "buy milk" in matches[0]["content"].lower()

def test_auto_scheduler_overlap(auto_scheduler):
    s1 = datetime(2026, 1, 2, 10, 0, 0)
    e1 = datetime(2026, 1, 2, 11, 0, 0)
    s2 = datetime(2026, 1, 2, 10, 30, 0)
    e2 = datetime(2026, 1, 2, 11, 30, 0)
    assert auto_scheduler._overlaps(s1, e1, s2, e2) is True

    s3 = datetime(2026, 1, 2, 12, 0, 0)
    e3 = datetime(2026, 1, 2, 13, 0, 0)
    assert auto_scheduler._overlaps(s1, e1, s3, e3) is False

@pytest.mark.asyncio
async def test_completion_verifier_detection(completion_verifier):
    task = SmartTask(id="1", user_id=123, content="Meet with Team")
    vtype = await completion_verifier.can_verify(task)
    assert vtype == "meeting"

    task2 = SmartTask(id="2", user_id=123, content="Buy groceries")
    vtype2 = await completion_verifier.can_verify(task2)
    assert vtype2 is None
