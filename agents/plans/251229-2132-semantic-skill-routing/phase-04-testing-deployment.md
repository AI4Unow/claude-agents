# Phase 4: Testing & Deployment

## Context

- Parent: [plan.md](plan.md)
- Depends on: Phase 1, 2, 3 complete
- Production: https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P1 |
| Effort | 30min |
| Status | pending |
| Review | pending |

Test semantic routing with sample messages and deploy to production.

## Key Insights

- Test all three intent paths: CHAT, SKILL, ORCHESTRATE
- Test explicit skill invocation with / and @
- Verify latency targets (<200ms overhead)
- Monitor logs for intent classification accuracy

## Requirements

1. Test explicit commands work
2. Test auto-detection routes correctly
3. Verify latency acceptable
4. Deploy and monitor production

## Test Cases

### Explicit Skill Invocation
| Input | Expected Skill | Expected Behavior |
|-------|---------------|-------------------|
| `/research quantum computing` | gemini-deep-research | Execute with "quantum computing" |
| `@design create a poster` | canvas-design | Execute with "create a poster" |
| `/code write a function` | backend-development | Execute with "write a function" |
| `/unknown xyz` | None | Fall through to intent classification |

### Auto Intent Detection
| Input | Expected Intent | Expected Behavior |
|-------|----------------|-------------------|
| "hello" | CHAT | Haiku direct response |
| "what is Python?" | CHAT | Haiku direct response |
| "research quantum computing in depth" | SKILL | gemini-deep-research |
| "design me a logo" | SKILL | canvas-design |
| "summarize this article" | SKILL | content or ai-multimodal |
| "build me a REST API with auth" | ORCHESTRATE | Full orchestrator |
| "plan the implementation" | ORCHESTRATE | Full orchestrator |

## Implementation Steps

1. Run local tests with sample messages
2. Add intent logging for monitoring
3. Deploy with `modal deploy main.py`
4. Test in production Telegram
5. Monitor logs for accuracy
6. Tune keywords/prompts if needed

## Todo List

- [ ] Test explicit /skill commands locally
- [ ] Test intent classification locally
- [ ] Deploy to Modal
- [ ] Test in Telegram production
- [ ] Monitor logs for errors
- [ ] Document any tuning needed

## Success Criteria

- [ ] All explicit commands work correctly
- [ ] >90% intent classification accuracy
- [ ] <200ms routing overhead
- [ ] No regression in existing functionality

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Production regression | High | Test thoroughly first |
| Wrong skill matched | Medium | Monitor and tune |
| Latency increase | Medium | Fast path optimization |

## Monitoring Commands

```bash
# Check health
curl -s https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run/health | jq .

# View logs
modal app logs claude-agents

# Deploy
modal deploy main.py
```

## Next Steps

After deployment:
1. Monitor for 24h
2. Collect intent classification stats
3. Tune keywords/prompts based on real usage
4. Consider adding more skill-specific trigger patterns
