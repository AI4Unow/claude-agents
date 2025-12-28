# Phase 6: Deploy & Monitor

## Context

- Plan: `./plan.md`
- Depends on: All previous phases complete

## Overview

- **Priority:** P1
- **Status:** Pending
- **Effort:** 2h

Deploy to Modal.com and set up monitoring for the self-improvement loop.

## Key Insights

- Modal deploy: `modal deploy agents/main.py`
- Modal logs: `modal app logs claude-agents`
- Firebase console for proposal monitoring
- Telegram notifications are real-time monitoring

## Requirements

### Functional
- Deploy updated code to Modal
- Configure ADMIN_TELEGRAM_ID secret
- Verify all endpoints work
- Monitor first few proposals

### Non-Functional
- Zero-downtime deployment (min_containers=1)
- Logs accessible for debugging
- Cost tracking for LLM improvement calls

## Pre-Deployment Checklist

- [ ] All phases 1-5 complete
- [ ] Tests pass locally
- [ ] ADMIN_TELEGRAM_ID added to admin-credentials secret
- [ ] No uncommitted changes in codebase
- [ ] Firebase indexes created (if needed)

## Deployment Steps

### Step 1: Update Modal Secrets

```bash
# Add admin Telegram ID to existing admin-credentials secret
modal secret create admin-credentials \
  ADMIN_TOKEN=your-existing-token \
  ADMIN_TELEGRAM_ID=your-telegram-user-id
```

### Step 2: Deploy

```bash
cd agents
modal deploy main.py
```

### Step 3: Verify Deployment

```bash
# Check logs
modal app logs claude-agents

# Test health endpoint
curl https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run/health
```

### Step 4: Test Improvement Flow

```bash
# Run test function
modal run main.py::test_improvement_flow
```

### Step 5: Monitor

- Check Telegram for notification
- Verify Firebase has proposal document
- Test approve/reject flow

## Monitoring Dashboard

### Firebase Collections to Monitor

| Collection | Purpose |
|------------|---------|
| `skill_improvements` | Improvement proposals |
| `telegram_sessions` | User sessions |
| `conversations` | Chat history |

### Key Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Proposals/hour | Firebase | > 10 = investigate |
| Approval rate | Firebase | < 50% = review prompts |
| Error rate | Modal logs | > 5% = investigate |
| Response time | Modal metrics | > 10s = investigate |

### Structlog Queries

```bash
# Find improvement events
modal app logs claude-agents | grep "improvement"

# Find errors
modal app logs claude-agents | grep "error"

# Find proposals
modal app logs claude-agents | grep "proposal"
```

## Rollback Plan

If issues arise:

1. **Quick rollback**: Revert to previous commit and redeploy
2. **Disable improvements**: Set rate limit to 0 temporarily
3. **Firebase cleanup**: Delete bad proposals manually

```bash
# Rollback to previous version
git checkout HEAD~1 -- agents/
modal deploy agents/main.py
```

## Cost Monitoring

### LLM Costs

Each improvement reflection ≈ 500 tokens
- Input: ~300 tokens (skill + error)
- Output: ~200 tokens (proposal)
- Cost: ~$0.002 per proposal

At max rate (3/hour/skill, ~25 skills):
- Worst case: 75 proposals/hour × $0.002 = $0.15/hour
- Monthly cap: ~$100 (unlikely, most skills won't error)

### Firebase Costs

- Reads: ~1000/day at peak (free tier covers)
- Writes: ~100/day (free tier covers)
- Storage: ~1MB (negligible)

## Post-Deployment Tasks

- [ ] Deploy to Modal
- [ ] Verify health endpoint
- [ ] Run test_improvement_flow
- [ ] Receive and approve test proposal
- [ ] Verify info.md updated
- [ ] Monitor for 24 hours
- [ ] Review first 5 real proposals
- [ ] Adjust prompts if needed
- [ ] Document any issues

## Success Criteria

- Deployment succeeds without errors
- Health endpoint returns healthy
- Test proposal created and notified
- Approve/reject flow works in production
- No increase in error rate
- Response time unchanged

## Troubleshooting Guide

### Proposal Not Created

1. Check rate limit: `modal app logs claude-agents | grep "rate_limited"`
2. Check deduplication: `modal app logs claude-agents | grep "duplicate"`
3. Check Firebase connection: `modal app logs claude-agents | grep "firebase"`

### Notification Not Received

1. Verify ADMIN_TELEGRAM_ID is correct
2. Check logs: `modal app logs claude-agents | grep "admin_telegram"`
3. Verify bot has permission to message admin

### Approve Button Fails

1. Check logs: `modal app logs claude-agents | grep "proposal_applied"`
2. Verify Volume commit: `modal app logs claude-agents | grep "commit"`
3. Check Firebase update: `modal app logs claude-agents | grep "approved"`

### Volume Commit Fails

1. Check Volume exists: `modal volume list`
2. Check permissions: Modal account settings
3. Retry manually via Modal console

## Documentation Updates

After successful deployment, update:

- [ ] `docs/deployment-guide.md` - Add improvement configuration
- [ ] `docs/project-roadmap.md` - Mark self-improvement as complete
- [ ] `README.md` - Add improvement section

## Next Steps

After successful deployment:

1. Monitor for 1 week
2. Review approval rate
3. Tune reflection prompts if needed
4. Consider Phase 2 enhancements:
   - Memory compaction
   - Multi-admin support
   - Rollback mechanism
