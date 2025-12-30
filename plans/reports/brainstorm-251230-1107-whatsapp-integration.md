# Brainstorm: WhatsApp Integration for Claude Agents

**Date:** 2024-12-30
**Status:** Agreed - Ready for Implementation Plan

## Problem Statement

Add WhatsApp as second UI/UX channel alongside existing Telegram integration, enabling agents to communicate with users via WhatsApp with full feature parity.

## Requirements Gathered

| Requirement | Value |
|-------------|-------|
| Use Case | Personal/Internal use |
| Scale | Low (<100 msgs/day) |
| Feature Parity | Full (text, voice, images, documents, commands) |
| Infrastructure | Modal-only (serverless) |

## Options Evaluated

### Option A: Neonize (Unofficial Protocol)
- **Mechanism:** Python wrapper around whatsmeow (Go), uses WhatsApp Multi-Device protocol via WebSocket
- **Pros:** Free, no verification, full features, works with personal account
- **Cons:** Ban risk, needs persistent connection (incompatible with Modal serverless), protocol breaks
- **Verdict:** Rejected - incompatible with Modal-only constraint

### Option B: Evolution API (Self-Hosted Service)
- **Mechanism:** Docker service exposing REST API, handles protocol internally
- **Pros:** Abstracts complexity, webhook-based, REST integration, multi-account
- **Cons:** Requires separate Docker host, additional infrastructure
- **Verdict:** Preferred but requires external hosting

### Option C: WhatsApp Cloud API (Official) - SELECTED
- **Mechanism:** Official Meta API via PyWa library
- **Pros:** No ban risk, stable, serverless-compatible, mirrors Telegram architecture
- **Cons:** Requires Meta Business verification, 24h messaging window, template approval for proactive messages
- **Verdict:** Best fit for Modal-only serverless architecture

## Final Recommended Solution

**WhatsApp Cloud API + PyWa Library**

### Rationale
1. Only option fully compatible with Modal serverless model
2. Mirrors existing Telegram webhook architecture exactly
3. No additional infrastructure required
4. Official API = no ban risk, stable long-term
5. PyWa integrates natively with FastAPI

### Architecture Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MODAL.COM                                    │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────┐    ┌────────────────────┐                   │
│  │ /webhook/telegram  │    │ /webhook/whatsapp  │                   │
│  └─────────┬──────────┘    └─────────┬──────────┘                   │
│            │                         │                               │
│            ▼                         ▼                               │
│  ┌─────────────────────────────────────────────────┐                │
│  │            Unified Message Handler              │                │
│  │  normalize_message() → process() → respond()    │                │
│  └─────────────────────────────────────────────────┘                │
│            │                         │                               │
│            ▼                         ▼                               │
│  ┌────────────────────┐    ┌────────────────────┐                   │
│  │ telegram.py        │    │ whatsapp.py        │                   │
│  └────────────────────┘    └────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Differences: Telegram vs WhatsApp Cloud

| Aspect | Telegram | WhatsApp Cloud |
|--------|----------|----------------|
| Verification | Secret token header | GET challenge + X-Hub-Signature-256 |
| Payload | Flat structure | Nested entry[0].changes[0].value |
| Formatting | HTML | Limited (bold, italic, code) |
| Interactive | Inline keyboards | Reply/list buttons |
| Media | file_id direct | Meta CDN upload/download |
| 24h window | N/A | Must respond within 24h |

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/services/whatsapp.py` | Create | Message formatting, media handling, send functions |
| `src/core/messaging.py` | Create | Platform-agnostic message abstraction |
| `main.py` | Modify | Add /webhook/whatsapp endpoint |
| `requirements.txt` | Modify | Add pywa library |

### Meta Setup Required (One-time Manual)

1. Create Meta Developer Account (developers.facebook.com)
2. Create App → Business type → Add WhatsApp product
3. Business Verification (submit documents)
4. Add dedicated phone number
5. Generate System User + Permanent Access Token
6. Configure webhook URL pointing to Modal

### Implementation Considerations

**Constraints:**
- 24-hour messaging window for conversations
- Template messages need Meta approval for proactive notifications
- Media requires CDN upload before sending
- Rate limits: 1000 unique users/day initially

**Risks:**
- Business verification can take days/weeks
- Need separate phone number (can't use personal)
- Template approval delays for notifications

**Mitigations:**
- Start verification process early
- Use test number during development
- Design around 24h window constraint

### Success Metrics

- WhatsApp messages processed end-to-end
- Feature parity: text, voice, images, documents
- Commands work identically across platforms
- Circuit breaker for WhatsApp API
- Trace logging for WhatsApp messages

## Next Steps

1. Create detailed implementation plan
2. Start Meta Business verification process (parallel)
3. Implement webhook endpoint
4. Create whatsapp.py service module
5. Abstract common messaging logic
6. Test with WhatsApp test number
7. Deploy and configure production webhook

## Unresolved Questions

1. Which phone number to use for WhatsApp Business?
2. What template messages needed for proactive notifications (e.g., local task completion)?
3. Should personalization system store WhatsApp-specific preferences?
