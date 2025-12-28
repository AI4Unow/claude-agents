---
title: "Additional Bot Tools"
description: "Add code execution, memory search, web reader, and datetime tools"
status: completed
completed: 2025-12-27
priority: P1
effort: 4h
branch: main
tags: [telegram, tools, rag, code-execution]
created: 2025-12-27
---

# Additional Bot Tools

## Overview

Extend chatbot with 4 additional tools from validation feedback:
1. **Code Execution** - Run Python for calculations
2. **Memory/RAG Search** - Query Qdrant vector DB
3. **Web Page Reader** - Extract content from URLs
4. **DateTime Utilities** - Current time/date info

## Context

- [Smart Chatbot Plan](../251227-1234-smart-chatbot-tools/plan.md)
- Current tools: `src/tools/` (web_search implemented)

## Architecture

```
src/tools/
├── base.py           # Existing
├── registry.py       # Existing
├── web_search.py     # Existing
├── code_exec.py      # NEW: Python code execution
├── memory_search.py  # NEW: Qdrant RAG
├── web_reader.py     # NEW: URL content extraction
└── datetime_tool.py  # NEW: Date/time utilities
```

## Phases

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| 1 | DateTime Tool | 0.5h | pending |
| 2 | Code Execution Tool | 1h | pending |
| 3 | Web Page Reader | 1h | pending |
| 4 | Memory/RAG Search | 1.5h | pending |

## Security Considerations

- **Code Execution**: Sandboxed, timeout, no file/network access
- **Web Reader**: URL validation, content length limits
- **Memory Search**: Rate limiting for Qdrant queries

## Dependencies

- `httpx` (existing) - for web reader
- Qdrant service (existing) - for memory search
- Python `exec()` with restrictions - for code execution

## Success Criteria

1. All 4 tools registered and callable
2. Bot can answer "What time is it in Tokyo?"
3. Bot can calculate "What is 15% of 847?"
4. Bot can summarize a URL content
5. Bot can recall previous conversation context
