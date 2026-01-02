
import pytest
from datetime import datetime, time, timezone
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add agents directory to path
sys.path.insert(0, os.path.abspath('agents'))

from src.core.nlp_parser import parse_task, ParsedTask, _detect_recurrence
from src.services.firebase.pkm import SmartTask, create_smart_task

@pytest.mark.asyncio
async def test_detect_recurrence():
    assert _detect_recurrence("every Monday") == "FREQ=WEEKLY;BYDAY=MO"
    assert _detect_recurrence("daily") == "FREQ=DAILY"
    assert _detect_recurrence("every weekday") == "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    assert _detect_recurrence("monthly") == "FREQ=MONTHLY"
    assert _detect_recurrence("once") is None

@pytest.mark.asyncio
async def test_parse_task_llm_fallback():
    # Test fallback when LLM fails
    current_time = datetime(2026, 1, 2, 10, 0, 0)

    with patch("src.core.nlp_parser.LLMClient") as mock_llm_class:
        mock_llm = mock_llm_class.return_value
        mock_llm.chat.side_effect = Exception("API Error")

        result = await parse_task("Buy milk tomorrow", current_time)

        assert result.content == "Buy milk tomorrow"
        assert result.intent == "task"
        assert result.confidence == 0.5

@pytest.mark.asyncio
async def test_create_smart_task_firebase():
    user_id = 12345
    content = "Test Smart Task"

    with patch("src.services.firebase.pkm.get_db") as mock_get_db:
        mock_db = mock_get_db.return_value
        mock_doc_ref = MagicMock()
        mock_doc = MagicMock()

        # Mocking the chain: db.collection().document().collection().document()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

        # Mocking get() to return a document with data
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "user_id": user_id,
            "content": content,
            "type": "task",
            "status": "inbox",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        mock_doc_ref.get.return_value = mock_doc

        task = await create_smart_task(user_id, content, priority="p1")

        assert task.content == content
        assert task.user_id == user_id
        mock_doc_ref.set.assert_called_once()
