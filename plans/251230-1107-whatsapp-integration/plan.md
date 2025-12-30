# WhatsApp Cloud API Integration Plan

**Created:** 2024-12-30
**Status:** Ready for Implementation
**Brainstorm:** [brainstorm-251230-1107-whatsapp-integration.md](../reports/brainstorm-251230-1107-whatsapp-integration.md)

## Overview

Add WhatsApp as second UI/UX channel alongside Telegram using WhatsApp Cloud API + PyWa library. Serverless-compatible, mirrors existing Telegram webhook architecture.

## Requirements

| Requirement | Value |
|-------------|-------|
| Use Case | Personal/Internal use |
| Scale | Low (<100 msgs/day) |
| Feature Parity | Full (text, voice, images, documents, commands) |
| Infrastructure | Modal-only (serverless) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MODAL.COM                                    │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────┐    ┌────────────────────┐                   │
│  │ /webhook/telegram  │    │ /webhook/whatsapp  │  ← NEW            │
│  └─────────┬──────────┘    └─────────┬──────────┘                   │
│            │                         │                               │
│            └──────────┬──────────────┘                               │
│                       ▼                                              │
│  ┌─────────────────────────────────────────────────┐                │
│  │      Unified Messaging Layer (messaging.py)     │  ← NEW         │
│  │  • NormalizedMessage dataclass                  │                │
│  │  • Platform adapter interface                   │                │
│  └─────────────────────────────────────────────────┘                │
│                       │                                              │
│                       ▼                                              │
│  ┌─────────────────────────────────────────────────┐                │
│  │           Existing Message Processing           │                │
│  │  • process_message() • handle_command()         │                │
│  │  • handle_voice_message() • handle_image_message()               │
│  └─────────────────────────────────────────────────┘                │
│            │                         │                               │
│            ▼                         ▼                               │
│  ┌────────────────────┐    ┌────────────────────┐                   │
│  │ telegram.py        │    │ whatsapp.py        │  ← NEW            │
│  │ (format/send)      │    │ (format/send)      │                   │
│  └────────────────────┘    └────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Meta Setup & Secrets
**File:** [phase-01-meta-setup.md](phase-01-meta-setup.md)
- Meta Developer Account creation
- WhatsApp Business App setup
- Test number configuration
- Modal secrets creation

### Phase 2: Webhook Endpoint
**File:** [phase-02-webhook-endpoint.md](phase-02-webhook-endpoint.md)
- GET verification handler
- POST message handler
- X-Hub-Signature-256 validation
- Rate limiting

### Phase 3: WhatsApp Service Module
**File:** [phase-03-whatsapp-service.md](phase-03-whatsapp-service.md)
- Message formatting (markdown to WhatsApp)
- Send message functions
- Media download/upload
- Error handling

### Phase 4: Unified Messaging Abstraction
**File:** [phase-04-messaging-abstraction.md](phase-04-messaging-abstraction.md)
- NormalizedMessage dataclass
- Platform adapter interface
- Refactor Telegram to use abstraction
- Wire WhatsApp to abstraction

### Phase 5: Feature Parity (Media)
**File:** [phase-05-media-handling.md](phase-05-media-handling.md)
- Voice message handling
- Image handling
- Document handling
- Reply buttons

### Phase 6: Testing & Deployment
**File:** [phase-06-testing-deployment.md](phase-06-testing-deployment.md)
- Test with WhatsApp test number
- Circuit breaker for WhatsApp
- Trace logging
- Production webhook setup

## Key Differences: Telegram vs WhatsApp

| Aspect | Telegram | WhatsApp Cloud |
|--------|----------|----------------|
| Verification | Secret token header | GET challenge + X-Hub-Signature-256 |
| Payload | `message.text` | `entry[0].changes[0].value.messages[0]` |
| User ID | `message.from.id` (int) | `messages[0].from` (phone string) |
| Formatting | HTML tags | Limited: `*bold*`, `_italic_`, ``` `code` ``` |
| Keyboards | InlineKeyboard | Reply buttons / List buttons |
| Media | file_id → getFile | media_id → GET media URL → download |
| 24h window | N/A | Must respond within 24h |

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/services/whatsapp.py` | Create | Message formatting, media handling, send |
| `src/core/messaging.py` | Create | Platform-agnostic abstraction |
| `main.py` | Modify | Add /webhook/whatsapp endpoint |
| `src/core/resilience.py` | Modify | Add whatsapp circuit breaker |
| `requirements.txt` | Modify | Add pywa[fastapi] |

## Secrets Required

```bash
modal secret create whatsapp-credentials \
  WHATSAPP_TOKEN=<permanent_access_token> \
  WHATSAPP_PHONE_ID=<phone_number_id> \
  WHATSAPP_BUSINESS_ID=<business_account_id> \
  WHATSAPP_APP_SECRET=<app_secret_for_signature> \
  WHATSAPP_VERIFY_TOKEN=<webhook_verify_token>
```

## Constraints & Risks

### Constraints
- **24h Window:** Can only respond to users within 24h of their last message
- **Templates:** Proactive messages require Meta-approved templates
- **Rate Limits:** 1000 unique users/day initially
- **Media:** Must download from Meta CDN, can't direct link

### Risks
| Risk | Mitigation |
|------|------------|
| Business verification delays | Start early, use test number |
| Template approval delays | Design for 24h response pattern |
| Different user IDs (phone vs int) | Normalize in messaging layer |

## Success Criteria

- [ ] WhatsApp webhook receives and responds to messages
- [ ] Text, voice, image, document messages work
- [ ] Commands work identically to Telegram
- [ ] Circuit breaker protects WhatsApp API
- [ ] Traces logged for WhatsApp interactions
- [ ] Personalization works with WhatsApp users

## Dependencies

- Meta Business verification (manual, parallel task)
- Dedicated phone number for WhatsApp Business
- Modal secrets configured

## Estimated Effort

| Phase | Complexity |
|-------|------------|
| Phase 1 | Low (manual setup) |
| Phase 2 | Medium |
| Phase 3 | Medium |
| Phase 4 | High (refactoring) |
| Phase 5 | Medium |
| Phase 6 | Low |
