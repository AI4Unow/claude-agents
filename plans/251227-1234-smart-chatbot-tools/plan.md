---
title: "Smart Chatbot with Tool Capabilities"
description: "Add tool use, web search, and agentic loop to Telegram chatbot"
status: completed
completed: 2025-12-27
priority: P1
effort: 6h
branch: main
tags: [telegram, tools, anthropic, tavily, agentic]
created: 2025-12-27
---

# Smart Chatbot with Tool Capabilities

## Overview

Enhance Telegram chatbot with Anthropic tool_use capability, web search via Tavily, and agentic loop for multi-step reasoning.

## Context

- [Research: Anthropic Tool Use](./research/researcher-01-anthropic-tool-use.md)
- [Research: Web Search APIs](./research/researcher-02-web-search-apis.md)

## Architecture

```
User Message → LLM (with tools) → Tool Call?
                                    ↓ Yes
                              Execute Tool → Append Result → Loop
                                    ↓ No
                              Return Final Response
```

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Tool Registry | `src/tools/registry.py` | Define/register tools |
| Web Search | `src/tools/web_search.py` | Tavily integration |
| LLM Service | `src/services/llm.py` | Add tool support |
| Agentic Loop | `src/services/agentic.py` | Iteration logic |

## Phases

| Phase | Description | Effort | Link |
|-------|-------------|--------|------|
| 1 | Tool System Architecture | 1.5h | [phase-01](./phase-01-tool-system.md) |
| 2 | Web Search Integration | 1.5h | [phase-02](./phase-02-web-search.md) |
| 3 | Agentic Loop Implementation | 2h | [phase-03](./phase-03-agentic-loop.md) |
| 4 | Testing & Deployment | 1h | [phase-04](./phase-04-testing-deployment.md) |

## Cost Controls

- Max 5 iterations per request
- Cache Tavily results (15min TTL)
- Limit tool results to 2000 chars
- Use `search_depth="basic"` by default

## Success Criteria

1. Bot answers "What's the weather in Hanoi today?" with current data
2. Multi-step queries complete within 5 iterations
3. Graceful fallback when tools fail
4. No breaking changes to existing commands

## Risks

| Risk | Mitigation |
|------|------------|
| Infinite loops | Max iteration limit |
| API cost spike | Rate limiting + caching |
| Tavily downtime | Fallback to Serper |

## Dependencies

- `exa-py` package (primary search)
- `tavily-python` package (fallback)
- `EXA_API_KEY` secret in Modal
- `TAVILY_API_KEY` secret in Modal (fallback)

## Validation Summary

**Validated:** 2025-12-27
**Questions asked:** 6

### Confirmed Decisions
- **Primary search API:** Exa (neural search, meaning-based)
- **Fallback provider:** Tavily (LLM-optimized fallback)
- **Max iterations:** 5 (balance of capability and cost)
- **Cache TTL:** 15 minutes
- **Error display:** Brief error message to user

### Future Tools Planned
- Code execution (Python calculations)
- Memory/RAG search (Qdrant integration)
- Web page reader (URL content extraction)
- Date/time utilities

### Action Items
- [ ] Update phase-02 to use Exa as primary, Tavily as fallback
- [ ] Add `exa-py` to requirements.txt
- [ ] Create `EXA_API_KEY` Modal secret
