# Phase 4: Vercel Edge Webhooks

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 3 - Qdrant Cloud Setup](./phase-03-qdrant-vector-memory.md)

## Overview

**Priority:** P1 - Gateway Layer
**Status:** Pending
**Effort:** 2h

Deploy Vercel Edge Functions as the webhook gateway. Handles Telegram and GitHub webhooks with low latency, signature verification, and smart routing to Modal agents.

## Requirements

### Functional
- Receive Telegram webhooks (optional, can use Modal directly)
- Receive GitHub webhooks (for skills sync)
- Verify signatures for security
- Route to appropriate Modal functions
- Return immediate ACK (<100ms)

### Non-Functional
- Edge deployment (global, low latency)
- Zero cold start
- Free tier sufficient

## Architecture

```
                    TELEGRAM API            GITHUB
                         │                      │
                         ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VERCEL EDGE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  /api/webhook/telegram     /api/webhook/github                  │
│  ├─ Parse update           ├─ Verify signature                 │
│  ├─ Route by type          ├─ Check branch                     │
│  └─ Call Modal agent       ├─ Trigger skills sync              │
│                            └─ Return ACK                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
                    MODAL.COM
                  (Agent Workers)
```

## Project Structure

```
vercel/
├── package.json
├── vercel.json
├── api/
│   └── webhook/
│       └── telegram.ts       # Telegram webhook handler (optional)
│       └── github.ts         # GitHub webhook handler
└── lib/
    ├── verify.ts             # Signature verification
    └── modal.ts              # Modal client
```

## Implementation Steps

### 1. Initialize Vercel Project

```bash
mkdir vercel && cd vercel
npm init -y
npm install
```

### 2. Create package.json

```json
{
  "name": "claude-agents-webhooks",
  "private": true,
  "scripts": {
    "dev": "vercel dev",
    "deploy": "vercel --prod"
  },
  "dependencies": {
    "@vercel/edge": "^1.0.0"
  }
}
```

### 3. Create vercel.json

```json
{
  "functions": {
    "api/**/*.ts": {
      "runtime": "edge"
    }
  },
  "env": {
    "TELEGRAM_BOT_TOKEN": "@telegram-bot-token",
    "GITHUB_WEBHOOK_SECRET": "@github-webhook-secret",
    "MODAL_TOKEN_ID": "@modal-token-id",
    "MODAL_TOKEN_SECRET": "@modal-token-secret"
  }
}
```

### 4. Create lib/verify.ts

```typescript
import { createHmac, timingSafeEqual } from 'crypto';

export function verifyTelegramUpdate(
  body: string,
  token: string
): boolean {
  // Telegram doesn't sign webhook payloads
  // Instead, use a secret path or validate bot token in payload
  // For security, use secret webhook URL path
  return true;  // Validate via secret URL path instead
}

export function verifyGitHubSignature(
  body: string,
  signature: string,
  secret: string
): boolean {
  const expected = 'sha256=' + createHmac('sha256', secret)
    .update(body)
    .digest('hex');

  try {
    return timingSafeEqual(
      Buffer.from(expected),
      Buffer.from(signature)
    );
  } catch {
    return false;
  }
}
```

### 5. Create lib/modal.ts

```typescript
const MODAL_API_URL = 'https://api.modal.com/v1';

interface ModalCallOptions {
  functionName: string;
  payload: Record<string, unknown>;
}

export async function callModalFunction(options: ModalCallOptions) {
  const { functionName, payload } = options;

  const tokenId = process.env.MODAL_TOKEN_ID;
  const tokenSecret = process.env.MODAL_TOKEN_SECRET;

  // Call Modal function via web endpoint
  // Note: You'll need to expose Modal functions as web endpoints
  const response = await fetch(
    `https://your-modal-app--${functionName}.modal.run`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  );

  return response.json();
}

// Fire-and-forget call (don't wait for response)
export function triggerModalFunction(options: ModalCallOptions) {
  // Start the request but don't await it
  callModalFunction(options).catch(console.error);
}
```

### 6. Create api/webhook/telegram.ts (Optional - Modal handles this directly)

```typescript
// Note: Telegram webhooks are typically handled directly by Modal
// This is optional if you want to route through Vercel for observability

import { triggerModalFunction } from '../../lib/modal';

export const config = {
  runtime: 'edge',
};

export default async function handler(request: Request) {
  if (request.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  const body = await request.text();
  const update = JSON.parse(body);

  // Extract message info
  const message = update.message || {};
  const text = message.text || '';

  // Determine which Modal function to call
  let functionName = 'telegram-chat-agent';

  // Smart routing based on message content
  if (text.toLowerCase().includes('github') || text.toLowerCase().includes('repo')) {
    functionName = 'github-agent';
  } else if (text.toLowerCase().includes('report') || text.toLowerCase().includes('data')) {
    functionName = 'data-agent';
  }

  // Trigger Modal function (fire-and-forget for speed)
  triggerModalFunction({
    functionName,
    payload: update,
  });

  // Immediate ACK to Telegram
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
```

### 7. Create api/webhook/github.ts

```typescript
import { verifyGitHubSignature } from '../../lib/verify';
import { triggerModalFunction } from '../../lib/modal';

export const config = {
  runtime: 'edge',
};

export default async function handler(request: Request) {
  if (request.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  const body = await request.text();
  const signature = request.headers.get('X-Hub-Signature-256') || '';
  const secret = process.env.GITHUB_WEBHOOK_SECRET || '';

  // Verify signature
  if (!verifyGitHubSignature(body, signature, secret)) {
    return new Response('Invalid signature', { status: 401 });
  }

  const payload = JSON.parse(body);
  const ref = payload.ref || '';

  // Only sync on push to main branch
  if (ref === 'refs/heads/main') {
    triggerModalFunction({
      functionName: 'sync-skills-from-github',
      payload: { triggered_by: 'webhook' },
    });

    return new Response(JSON.stringify({ status: 'sync_triggered' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return new Response(JSON.stringify({ status: 'ignored', ref }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}
```

### 8. Deploy to Vercel

```bash
# Login to Vercel
vercel login

# Set secrets
vercel secrets add telegram-bot-token "your-telegram-token"
vercel secrets add github-webhook-secret "your-github-secret"
vercel secrets add modal-token-id "your-modal-token-id"
vercel secrets add modal-token-secret "your-modal-token-secret"

# Deploy
vercel --prod
```

### 9. Configure Webhooks

**Telegram Bot (optional - if using Vercel routing):**
1. Message @BotFather in Telegram
2. Get bot token
3. Set webhook URL: `https://your-project.vercel.app/api/webhook/telegram`
4. Or use Modal webhook directly (recommended)

**GitHub:**
1. Go to your repo → Settings → Webhooks
2. Add webhook
3. URL: `https://your-project.vercel.app/api/webhook/github`
4. Secret: Same as `github-webhook-secret`
5. Events: Just the `push` event

## Files to Create

| Path | Action | Description |
|------|--------|-------------|
| `vercel/package.json` | Create | Package config |
| `vercel/vercel.json` | Create | Vercel config |
| `vercel/lib/verify.ts` | Create | Signature verification |
| `vercel/lib/modal.ts` | Create | Modal client |
| `vercel/api/webhook/telegram.ts` | Create | Telegram webhook (optional) |
| `vercel/api/webhook/github.ts` | Create | GitHub webhook |

## Todo List

- [ ] Create Vercel project
- [ ] Create webhook handlers
- [ ] Configure Vercel secrets
- [ ] Deploy to Vercel
- [ ] Configure Telegram webhook URL (if using Vercel routing)
- [ ] Configure GitHub webhook URL
- [ ] Test end-to-end flow

## Success Criteria

- [ ] Telegram webhook responds <100ms (if used)
- [ ] GitHub webhook triggers skills sync
- [ ] Signature verification works
- [ ] Modal functions called correctly

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Vercel cold start | Latency spike | Edge runtime has zero cold start |
| Modal call fails | Message lost | Log errors, add retry queue |
| Signature bypass | Security breach | Strict verification, no fallback |

## Security Considerations

- Always verify signatures before processing
- Use Vercel secrets, never hardcode
- Log suspicious requests
- Rate limit by IP if needed

## Next Steps

After completing this phase:
1. Proceed to Phase 5: Telegram Chat Agent
2. Test webhook → Modal flow
