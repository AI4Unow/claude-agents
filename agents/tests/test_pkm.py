"""PKM system tests."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

import sys
sys.path.insert(0, 'agents')


# ==================== Test PKM Firebase CRUD ====================

class TestPKMFirebase:
    """Test Firebase CRUD operations for PKM items."""

    @pytest.mark.asyncio
    async def test_create_item(self):
        """Create item, verify fields are set correctly."""
        from src.services.firebase.pkm import create_item, PKMItem

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            # Mock Firebase
            mock_doc_ref = MagicMock()
            mock_doc = MagicMock()
            mock_doc.to_dict.return_value = {
                "user_id": 123,
                "content": "Test note",
                "type": "note",
                "status": "inbox",
                "tags": ["test"],
                "source": "telegram",
                "created_at": datetime(2025, 12, 30),
                "updated_at": datetime(2025, 12, 30),
            }
            mock_doc_ref.get.return_value = mock_doc

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

            # Create item
            item = await create_item(
                user_id=123,
                content="Test note",
                item_type="note",
                tags=["test"]
            )

            # Verify
            assert isinstance(item, PKMItem)
            assert item.user_id == 123
            assert item.content == "Test note"
            assert item.type == "note"
            assert item.status == "inbox"
            assert "test" in item.tags
            mock_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_item(self):
        """Get by ID returns correct item."""
        from src.services.firebase.pkm import get_item

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            # Mock Firebase
            mock_doc = MagicMock()
            mock_doc.exists = True
            mock_doc.to_dict.return_value = {
                "user_id": 123,
                "content": "Test task",
                "type": "task",
                "status": "active",
                "tags": ["work"],
                "priority": "high",
                "source": "telegram",
            }

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

            # Get item
            item = await get_item(user_id=123, item_id="item-123")

            # Verify
            assert item is not None
            assert item.id == "item-123"
            assert item.type == "task"
            assert item.priority == "high"

    @pytest.mark.asyncio
    async def test_get_item_not_found(self):
        """Get non-existent item returns None."""
        from src.services.firebase.pkm import get_item

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            mock_doc = MagicMock()
            mock_doc.exists = False

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

            item = await get_item(user_id=123, item_id="nonexistent")
            assert item is None

    @pytest.mark.asyncio
    async def test_update_item(self):
        """Update fields, verify changes."""
        from src.services.firebase.pkm import update_item

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            # Mock existing doc
            mock_doc = MagicMock()
            mock_doc.exists = True
            mock_doc.get.return_value = "inbox"

            # Mock updated doc
            mock_updated_doc = MagicMock()
            mock_updated_doc.to_dict.return_value = {
                "user_id": 123,
                "content": "Updated content",
                "type": "task",
                "status": "active",
                "tags": ["updated"],
                "source": "telegram",
            }

            mock_doc_ref = MagicMock()
            mock_doc_ref.get.side_effect = [mock_doc, mock_updated_doc]

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

            # Update
            item = await update_item(
                user_id=123,
                item_id="item-123",
                content="Updated content",
                status="active",
                tags=["updated"]
            )

            # Verify
            assert item is not None
            assert item.content == "Updated content"
            assert item.status == "active"
            mock_doc_ref.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_item_auto_completes(self):
        """Status change to done auto-sets completed_at."""
        from src.services.firebase.pkm import update_item
        from firebase_admin import firestore

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            mock_doc = MagicMock()
            mock_doc.exists = True
            mock_doc.get.return_value = "active"  # Current status

            mock_updated_doc = MagicMock()
            mock_updated_doc.to_dict.return_value = {
                "user_id": 123,
                "content": "Task",
                "type": "task",
                "status": "done",
                "source": "telegram",
                "completed_at": datetime(2025, 12, 30),
            }

            mock_doc_ref = MagicMock()
            mock_doc_ref.get.side_effect = [mock_doc, mock_updated_doc]

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

            # Update to done
            item = await update_item(user_id=123, item_id="item-123", status="done")

            # Verify completed_at was set
            assert item.status == "done"
            assert item.completed_at is not None

            # Verify update call included completed_at
            call_args = mock_doc_ref.update.call_args[0][0]
            assert "completed_at" in call_args

    @pytest.mark.asyncio
    async def test_delete_item(self):
        """Delete item, verify gone."""
        from src.services.firebase.pkm import delete_item

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            mock_doc = MagicMock()
            mock_doc.exists = True

            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

            # Delete
            result = await delete_item(user_id=123, item_id="item-123")

            # Verify
            assert result is True
            mock_doc_ref.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_item_not_found(self):
        """Delete non-existent item returns False."""
        from src.services.firebase.pkm import delete_item

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            mock_doc = MagicMock()
            mock_doc.exists = False

            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

            result = await delete_item(user_id=123, item_id="nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_list_items_filter_status(self):
        """Filter by status returns matching items."""
        from src.services.firebase.pkm import list_items

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            # Mock query results
            mock_doc1 = MagicMock()
            mock_doc1.id = "item-1"
            mock_doc1.to_dict.return_value = {
                "user_id": 123,
                "content": "Inbox item",
                "type": "note",
                "status": "inbox",
                "tags": [],
                "source": "telegram",
            }

            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.stream.return_value = [mock_doc1]

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value = mock_query

            # List inbox items
            items = await list_items(user_id=123, status="inbox")

            # Verify
            assert len(items) == 1
            assert items[0].status == "inbox"

    @pytest.mark.asyncio
    async def test_list_items_filter_type(self):
        """Filter by type returns matching items."""
        from src.services.firebase.pkm import list_items

        with patch("src.services.firebase.pkm.get_db") as mock_db:
            mock_doc1 = MagicMock()
            mock_doc1.id = "task-1"
            mock_doc1.to_dict.return_value = {
                "user_id": 123,
                "content": "Task",
                "type": "task",
                "status": "active",
                "tags": [],
                "source": "telegram",
            }

            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.stream.return_value = [mock_doc1]

            mock_db.return_value.collection.return_value.document.return_value.collection.return_value = mock_query

            # List tasks
            items = await list_items(user_id=123, item_type="task")

            # Verify
            assert len(items) == 1
            assert items[0].type == "task"


# ==================== Test PKM Qdrant Operations ====================

class TestPKMQdrant:
    """Test Qdrant vector operations for PKM."""

    @pytest.mark.asyncio
    async def test_store_and_search(self):
        """Store item, search returns it."""
        from src.services.qdrant import store_pkm_item, search_pkm_items

        with patch("src.services.qdrant.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock search result
            mock_result = MagicMock()
            mock_result.payload = {
                "item_id": "item-123",
                "type": "note",
                "status": "active",
                "tags": ["test"],
                "content_preview": "Test content"
            }
            mock_result.score = 0.95
            mock_client.search.return_value = [mock_result]

            # Store item
            embedding = [0.1] * 3072
            stored = await store_pkm_item(
                user_id=123,
                item_id="item-123",
                content="Test content",
                embedding=embedding,
                item_type="note",
                status="active",
                tags=["test"]
            )

            assert stored is True

            # Search
            results = await search_pkm_items(
                user_id=123,
                embedding=embedding,
                limit=5
            )

            # Verify
            assert len(results) == 1
            assert results[0]["item_id"] == "item-123"
            assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_user_isolation(self):
        """User A can't find User B's items."""
        from src.services.qdrant import search_pkm_items

        with patch("src.services.qdrant.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            # Mock returns empty for user 456
            mock_client.search.return_value = []

            embedding = [0.1] * 3072
            results = await search_pkm_items(
                user_id=456,
                embedding=embedding,
                limit=5
            )

            # Verify no results for different user
            assert len(results) == 0

            # Verify filter was applied
            call_args = mock_client.search.call_args
            assert call_args[1]["query_filter"] is not None


# ==================== Test PKM Classification ====================

class TestPKMClassification:
    """Test AI classification of content."""

    @pytest.mark.asyncio
    async def test_classify_task(self):
        """Task-like content classified as task."""
        from src.services.pkm import classify_item

        with patch("src.services.pkm.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.return_value = '{"type":"task","tags":["groceries"],"priority":"medium","has_deadline":false}'
            mock_llm.return_value = mock_client

            result = await classify_item("Buy groceries for dinner")

            assert result["type"] == "task"
            assert "groceries" in result["tags"]
            assert result["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_classify_link(self):
        """URL content classified as link."""
        from src.services.pkm import classify_item

        with patch("src.services.pkm.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.return_value = '{"type":"link","tags":["documentation","ai"],"priority":null,"has_deadline":false}'
            mock_llm.return_value = mock_client

            result = await classify_item("https://docs.anthropic.com/claude")

            assert result["type"] == "link"
            assert "documentation" in result["tags"]

    @pytest.mark.asyncio
    async def test_classify_note(self):
        """Meeting notes classified as note."""
        from src.services.pkm import classify_item

        with patch("src.services.pkm.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.return_value = '{"type":"note","tags":["meeting","project-x"],"priority":null,"has_deadline":false}'
            mock_llm.return_value = mock_client

            result = await classify_item("Meeting notes: Discussed project X timeline")

            assert result["type"] == "note"
            assert "meeting" in result["tags"]

    @pytest.mark.asyncio
    async def test_classify_idea(self):
        """Speculative content classified as idea."""
        from src.services.pkm import classify_item

        with patch("src.services.pkm.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.return_value = '{"type":"idea","tags":["product","innovation"],"priority":"low","has_deadline":false}'
            mock_llm.return_value = mock_client

            result = await classify_item("What if we automated the entire onboarding flow?")

            assert result["type"] == "idea"
            assert "innovation" in result["tags"]

    @pytest.mark.asyncio
    async def test_classify_quote(self):
        """Quote with attribution classified as quote."""
        from src.services.pkm import classify_item

        with patch("src.services.pkm.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.return_value = '{"type":"quote","tags":["wisdom","philosophy"],"priority":null,"has_deadline":false}'
            mock_llm.return_value = mock_client

            result = await classify_item('"The only way to do great work is to love what you do." - Steve Jobs')

            assert result["type"] == "quote"
            assert "wisdom" in result["tags"]

    @pytest.mark.asyncio
    async def test_classify_fallback_on_error(self):
        """Classification error falls back to note."""
        from src.services.pkm import classify_item

        with patch("src.services.pkm.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.chat.side_effect = Exception("API error")
            mock_llm.return_value = mock_client

            result = await classify_item("Some content")

            # Fallback to note
            assert result["type"] == "note"
            assert result["tags"] == []
            assert result["priority"] is None


# ==================== Test PKM Integration ====================

class TestPKMIntegration:
    """Test full PKM workflows."""

    @pytest.mark.asyncio
    async def test_save_and_find(self):
        """Save -> classify -> find workflow."""
        from src.services.pkm import save_item, find_items

        with patch("src.services.pkm.classify_item") as mock_classify, \
             patch("src.services.pkm.create_item") as mock_create, \
             patch("src.services.pkm.get_embedding") as mock_embed, \
             patch("src.services.pkm.store_pkm_item") as mock_store, \
             patch("src.services.pkm.get_query_embedding") as mock_query_embed, \
             patch("src.services.pkm.search_pkm_items") as mock_search, \
             patch("src.services.pkm.get_item") as mock_get:

            # Mock classification
            mock_classify.return_value = {
                "type": "task",
                "tags": ["work"],
                "priority": "high",
                "has_deadline": True
            }

            # Mock Firebase create
            from src.services.firebase.pkm import PKMItem
            mock_item = PKMItem(
                id="item-123",
                user_id=123,
                content="Complete quarterly report",
                type="task",
                status="inbox",
                tags=["work"],
                priority="high",
                source="telegram"
            )
            mock_create.return_value = mock_item

            # Mock embedding
            embedding = [0.1] * 3072
            mock_embed.return_value = embedding
            mock_query_embed.return_value = embedding

            # Mock Qdrant store
            mock_store.return_value = True

            # Save item
            item = await save_item(
                user_id=123,
                content="Complete quarterly report",
                source="telegram"
            )

            # Verify save flow
            assert item.id == "item-123"
            assert item.type == "task"
            mock_classify.assert_called_once()
            mock_create.assert_called_once()
            mock_store.assert_called_once()

            # Mock search results
            mock_search.return_value = [
                {
                    "item_id": "item-123",
                    "score": 0.95,
                    "type": "task",
                    "status": "inbox",
                    "tags": ["work"],
                    "content_preview": "Complete quarterly report"
                }
            ]
            mock_get.return_value = mock_item

            # Find item
            results = await find_items(user_id=123, query="quarterly report")

            # Verify find flow
            assert len(results) == 1
            assert results[0].id == "item-123"
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_inbox_workflow(self):
        """Save -> inbox -> process -> done workflow."""
        from src.services.pkm import save_item
        from src.services.firebase.pkm import get_inbox, update_item

        with patch("src.services.pkm.classify_item") as mock_classify, \
             patch("src.services.pkm.create_item") as mock_create, \
             patch("src.services.pkm.get_embedding") as mock_embed, \
             patch("src.services.pkm.store_pkm_item") as mock_store, \
             patch("src.services.firebase.pkm.get_db") as mock_db:

            # Mock classification
            mock_classify.return_value = {
                "type": "task",
                "tags": ["urgent"],
                "priority": "high",
                "has_deadline": False
            }

            # Mock Firebase create
            from src.services.firebase.pkm import PKMItem
            mock_item = PKMItem(
                id="task-1",
                user_id=123,
                content="Review PR",
                type="task",
                status="inbox",
                tags=["urgent"],
                priority="high",
                source="telegram"
            )
            mock_create.return_value = mock_item

            # Mock embedding and store
            mock_embed.return_value = [0.1] * 3072
            mock_store.return_value = True

            # Step 1: Save to inbox
            item = await save_item(user_id=123, content="Review PR")
            assert item.status == "inbox"
            assert item.id == "task-1"

            # Step 2: Get inbox (mock)
            mock_query = MagicMock()
            mock_doc = MagicMock()
            mock_doc.id = "task-1"
            mock_doc.to_dict.return_value = {
                "user_id": 123,
                "content": "Review PR",
                "type": "task",
                "status": "inbox",
                "tags": ["urgent"],
                "priority": "high",
                "source": "telegram",
            }
            mock_query.where.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.stream.return_value = [mock_doc]
            mock_db.return_value.collection.return_value.document.return_value.collection.return_value = mock_query

            inbox = await get_inbox(user_id=123)
            assert len(inbox) == 1
            assert inbox[0].status == "inbox"

            # Step 3: Process (move to active)
            mock_existing = MagicMock()
            mock_existing.exists = True
            mock_existing.get.return_value = "inbox"

            mock_updated = MagicMock()
            mock_updated.to_dict.return_value = {
                "user_id": 123,
                "content": "Review PR",
                "type": "task",
                "status": "active",
                "tags": ["urgent"],
                "priority": "high",
                "source": "telegram",
            }

            mock_doc_ref = MagicMock()
            mock_doc_ref.get.side_effect = [mock_existing, mock_updated]
            mock_db.return_value.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

            processed = await update_item(user_id=123, item_id="task-1", status="active")
            assert processed.status == "active"

            # Step 4: Mark done
            mock_done_check = MagicMock()
            mock_done_check.exists = True
            mock_done_check.get.return_value = "active"

            mock_done = MagicMock()
            mock_done.to_dict.return_value = {
                "user_id": 123,
                "content": "Review PR",
                "type": "task",
                "status": "done",
                "tags": ["urgent"],
                "priority": "high",
                "source": "telegram",
                "completed_at": datetime(2025, 12, 30),
            }

            mock_doc_ref.get.side_effect = [mock_done_check, mock_done]

            completed = await update_item(user_id=123, item_id="task-1", status="done")
            assert completed.status == "done"
            assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_save_embedding_failure_graceful(self):
        """Embedding failure doesn't block save."""
        from src.services.pkm import save_item

        with patch("src.services.pkm.classify_item") as mock_classify, \
             patch("src.services.pkm.create_item") as mock_create, \
             patch("src.services.pkm.get_embedding") as mock_embed, \
             patch("src.services.pkm.store_pkm_item") as mock_store:

            mock_classify.return_value = {
                "type": "note",
                "tags": [],
                "priority": None,
                "has_deadline": False
            }

            from src.services.firebase.pkm import PKMItem
            mock_item = PKMItem(
                id="note-1",
                user_id=123,
                content="Note",
                type="note",
                status="inbox",
                tags=[],
                source="telegram"
            )
            mock_create.return_value = mock_item

            # Embedding fails
            mock_embed.return_value = None

            # Should still save to Firebase
            item = await save_item(user_id=123, content="Note")

            assert item.id == "note-1"
            mock_create.assert_called_once()
            # Qdrant store should not be called
            mock_store.assert_not_called()
