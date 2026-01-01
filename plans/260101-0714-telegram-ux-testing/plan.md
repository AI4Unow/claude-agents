---
title: "UX Testing Framework for Telegram Bot"
description: "Comprehensive testing framework with live API tests, UX metrics collection, Telegram E2E simulation, and SLA dashboard"
status: completed
priority: P2
effort: 12h
branch: main
tags: [testing, ux, telegram, metrics, sla]
created: 2026-01-01
---

# UX Testing Framework for Telegram Bot

## Overview

This plan implements a comprehensive UX testing framework for the Telegram bot with four key components:

1. **Live API Tests** - Real API validation against production endpoints
2. **UX Metrics Collection** - Latency and success rate tracking in Firestore
3. **Telegram E2E Tests** - User journey simulation via Telethon
4. **SLA Dashboard** - Developer command for metrics visibility

## Architecture

```
+-------------------------------------------------------------------+
|                     UX TESTING FRAMEWORK                          |
+-------------------------------------------------------------------+
|                                                                    |
|  +-------------+   +-------------+   +-------------------------+  |
|  | Live API    |   | Telegram    |   | Metrics Collection      |  |
|  | Tests       |   | E2E         |   | (Firestore)             |  |
|  | (tests/live)|   | (tests/e2e) |   |                         |  |
|  |             |   | Telethon    |   | - Response latency      |  |
|  | - api.ai4u  |   |             |   | - Command success rate  |  |
|  | - Gemini    |   | - Onboard   |   | - Error classification  |  |
|  | - Exa/Tavily|   | - Commands  |   | - Circuit breaker stats |  |
|  | - Circuits  |   | - Flows     |   |                         |  |
|  +-------------+   +-------------+   +-------------------------+  |
|          |               |                    |                   |
|          +---------------+--------------------+                   |
|                          |                                        |
|             +-------------------------+                           |
|             |   /sla Command          |                           |
|             |   (commands/developer)  |                           |
|             +-------------------------+                           |
|                                                                    |
+-------------------------------------------------------------------+
```

## Phase Summary

| Phase | Focus | Effort | Priority |
|-------|-------|--------|----------|
| [Phase 1](./phase-01-live-api-tests.md) | Live API Tests | 3h | High |
| [Phase 2](./phase-02-ux-metrics.md) | UX Metrics Collection | 4h | High |
| [Phase 3](./phase-03-telegram-e2e.md) | Telegram E2E Tests | 4h | Medium |
| [Phase 4](./phase-04-sla-dashboard.md) | SLA Dashboard | 1h | Low |

## Key Decisions

1. **Telethon for E2E** - Real Telegram client simulation (not Bot API)
2. **Firestore for Metrics** - Collection `ux_metrics` with 30-day TTL
3. **Production Bot for E2E** - Test against real deployed bot
4. **Existing API Keys** - api.ai4u.now already configured, reuse
5. **New Credentials** - TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

## New Credentials Required

```bash
# Telethon E2E testing (from my.telegram.org)
modal secret update telegram-credentials \
  TELEGRAM_API_ID=... \
  TELEGRAM_API_HASH=... \
  TELEGRAM_PHONE=...
```

## File Structure

```
agents/
+-- tests/
|   +-- live/                     # Phase 1
|   |   +-- conftest.py           # @pytest.mark.live, env validation
|   |   +-- test_llm_live.py      # api.ai4u.now latency SLA
|   |   +-- test_gemini_live.py   # Grounding, deep research
|   |   +-- test_web_search_live.py  # 3-tier fallback
|   |   +-- test_circuits_live.py # Force failures, recovery
|   +-- e2e/                      # Phase 3
|   |   +-- conftest.py           # Telethon client setup
|   |   +-- test_onboarding.py    # /start -> /help -> /status
|   |   +-- test_commands.py      # All command responses
|   |   +-- test_skills.py        # Skill execution E2E
|   |   +-- test_media.py         # Voice, image handling
|   |   +-- test_error_recovery.py # Rate limits, timeouts
+-- src/services/firebase/
|   +-- ux_metrics.py             # Phase 2: UXMetricsService
+-- commands/
    +-- developer.py              # Phase 4: /sla command
```

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| api.ai4u.now P95 latency | < 5s | Live tests |
| Command success rate | > 99% | Metrics collection |
| E2E test coverage | > 80% flows | Test count |
| Circuit recovery time | < 60s | Live tests |
| Metrics collection overhead | < 50ms | Instrumentation |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Telethon auth complexity | Medium | Session file, documented setup |
| API costs from live tests | Low | Run sparingly, manual marker |
| Rate limiting during tests | Medium | Delays, dedicated test user |
| Metrics storage growth | Low | 30-day TTL on old metrics |

## Dependencies

- `telethon>=1.30.0` - Telegram E2E client
- Existing: pytest, pytest-asyncio, structlog

## Related Files

- `agents/tests/test_resilience.py` - Existing circuit breaker tests
- `agents/src/core/resilience.py` - Circuit breaker implementation
- `agents/src/services/llm.py` - LLM client to instrument
- `agents/commands/developer.py` - Add /sla command
- `agents/src/services/firebase/` - Add ux_metrics module

## Validation Summary

**Validated:** 2026-01-01
**Questions asked:** 4

### Confirmed Decisions

| Question | Decision |
|----------|----------|
| Test account | Dedicated test account (not personal) |
| SLA alerts | Yes, automatic Telegram notification on breach |
| E2E scope | All categories (Basic, Skills, Media, Admin) |
| P95 target | < 5 seconds |

### Action Items

- [ ] Update phase-04 to include SLA breach alerts to admin
- [ ] Update phase-03 to test all command categories (basic, skills, media, admin)

## Resolved Questions

1. ✅ Telethon tests use **dedicated test account** (not personal)
2. ✅ SLA alerts **will be sent** via Telegram to admin when thresholds breached
3. ✅ E2E tests cover **all command categories**: Basic, Skills, Media, Admin
