# Phase 4: Testing & Deployment

## Context

- [Plan Overview](./plan.md)
- [Phase 1: Tool System](./phase-01-tool-system.md)
- [Phase 2: Web Search](./phase-02-web-search.md)
- [Phase 3: Agentic Loop](./phase-03-agentic-loop.md)

## Overview

Test all components, deploy to Modal, and verify production behavior.

## Requirements

1. Unit tests for tool registry and web search
2. Integration test for agentic loop
3. Staging test before production
4. Rollback plan if issues

## Testing Strategy

### 4.1 Unit Tests

**File:** `agents/tests/test_tools.py`

```python
import pytest
from src.tools.base import BaseTool
from src.tools.registry import ToolRegistry

class MockTool(BaseTool):
    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"]
        }

    async def execute(self, params):
        return f"Received: {params.get('value')}"


@pytest.mark.asyncio
async def test_registry_register():
    registry = ToolRegistry()
    tool = MockTool()
    registry.register(tool)
    assert "mock_tool" in [t["name"] for t in registry.get_definitions()]


@pytest.mark.asyncio
async def test_registry_execute():
    registry = ToolRegistry()
    registry.register(MockTool())
    result = await registry.execute("mock_tool", {"value": "test"})
    assert "Received: test" in result


@pytest.mark.asyncio
async def test_registry_unknown_tool():
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {})
    assert "Error" in result
```

### 4.2 Web Search Test

**File:** `agents/tests/test_web_search.py`

```python
import pytest
import os

@pytest.mark.skipif(
    not os.environ.get("TAVILY_API_KEY"),
    reason="TAVILY_API_KEY not set"
)
@pytest.mark.asyncio
async def test_web_search_basic():
    from src.tools.web_search import WebSearchTool
    tool = WebSearchTool()
    result = await tool.execute({"query": "python programming"})
    assert len(result) > 0
    assert "Error" not in result


@pytest.mark.asyncio
async def test_web_search_empty_query():
    from src.tools.web_search import WebSearchTool
    tool = WebSearchTool()
    result = await tool.execute({"query": ""})
    assert "Error" in result
```

### 4.3 Integration Test

**File:** `agents/tests/test_agentic.py`

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio
async def test_agentic_loop_no_tools():
    """Test loop exits on end_turn without tool calls."""
    with patch("src.services.agentic.get_llm_client") as mock_llm:
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MagicMock(type="text", text="Hello!")]
        mock_llm.return_value.chat.return_value = mock_response

        from src.services.agentic import run_agentic_loop
        result = await run_agentic_loop("Hi")
        assert "Hello" in result
```

### 4.4 Local Test Commands

```bash
# Run unit tests
cd agents && pytest tests/ -v

# Test LLM with tools locally
modal run main.py::test_llm

# Test web search tool
TAVILY_API_KEY=xxx python -c "
import asyncio
from src.tools.web_search import WebSearchTool
result = asyncio.run(WebSearchTool().execute({'query': 'test'}))
print(result)
"
```

## Deployment Steps

### 4.5 Create Modal Secret

```bash
# Create Tavily secret
modal secret create tavily-credentials TAVILY_API_KEY=tvly-xxx

# Verify secrets
modal secret list
```

### 4.6 Deploy to Modal

```bash
cd agents

# Deploy (creates new version)
modal deploy main.py

# Check deployment
modal app list
```

### 4.7 Verify Webhook

```bash
# Check webhook is set correctly
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"

# Should show:
# "url": "https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run/webhook/telegram"
```

### 4.8 Production Test

Send test messages to Telegram bot:

1. `/start` - Should still work
2. `/help` - Should still work
3. `What's the weather in Hanoi today?` - Should use web search
4. `Tell me about recent AI news` - Should search and summarize

### 4.9 Rollback Plan

If issues in production:

```bash
# List deployments
modal app history claude-agents

# Rollback to previous
modal deploy main.py --tag previous-version
```

## Todo

- [ ] Create tests/ directory
- [ ] Write unit tests for registry
- [ ] Write unit tests for web search
- [ ] Write integration test for agentic loop
- [ ] Run local tests
- [ ] Create tavily-credentials secret
- [ ] Deploy to Modal
- [ ] Verify webhook
- [ ] Test in Telegram
- [ ] Monitor logs for errors

## Success Criteria

1. All unit tests pass
2. Deployment succeeds without errors
3. Bot responds to `/start`, `/help` (backward compatible)
4. Bot uses web search for current info queries
5. No errors in Modal logs during normal operation
6. Response time < 30s for tool-using queries

## Monitoring

```bash
# Watch logs
modal logs claude-agents -f

# Check for errors
modal logs claude-agents | grep -i error
```

## Unresolved Questions

1. Rate limiting strategy if bot gets popular?
2. Should we add usage tracking/billing alerts?
3. Multiple tools in future - how to guide tool selection?
