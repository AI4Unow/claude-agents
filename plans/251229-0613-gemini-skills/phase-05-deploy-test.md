# Phase 5: Deploy & Test

**Status:** Pending
**Depends on:** Phase 4
**Files:** `main.py`

---

## Tasks

### 5.1 Pre-Deploy Checklist

- [ ] GCP secrets configured: `modal secret list | grep gcp`
- [ ] All 4 skill info.md files exist
- [ ] `gemini.py` service created
- [ ] `gemini_tools.py` handlers created
- [ ] `resilience.py` has gemini_circuit
- [ ] main.py routing updated
- [ ] google-genai in Modal image

---

### 5.2 Deploy

```bash
cd /Users/nad/Library/CloudStorage/OneDrive-Personal/Agents

# Deploy to Modal
modal deploy agents/main.py

# Check deployment logs
modal app logs claude-agents --limit 50
```

---

### 5.3 Test Commands

```bash
# Test Gemini client
modal run agents/main.py::test_gemini

# Test grounding
modal run agents/main.py::test_grounding

# Test deep research
modal run agents/main.py::test_deep_research
```

---

### 5.4 API Tests

```bash
BASE_URL="https://duc-a-nguyen--claude-agents-telegramchatagent-app.modal.run"

# Health check
curl $BASE_URL/health | jq

# List skills (verify Gemini skills)
curl $BASE_URL/api/skills | jq '.[] | select(.name | contains("gemini"))'

# Test deep research
curl -X POST $BASE_URL/api/skill \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "gemini-deep-research",
    "task": "Research Modal.com deployment patterns",
    "context": {"max_iterations": 2}
  }' | jq

# Test grounding
curl -X POST $BASE_URL/api/skill \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "gemini-grounding",
    "task": "What is the current price of Ethereum?"
  }' | jq

# Test thinking
curl -X POST $BASE_URL/api/skill \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "gemini-thinking",
    "task": "Explain the CAP theorem with examples",
    "context": {"thinking_level": "high"}
  }' | jq

# Check circuit status
curl $BASE_URL/api/circuits | jq '.gemini_api'
```

---

### 5.5 Telegram Test

Send these messages to your Telegram bot:

1. **Deep Research:**
   ```
   /skill gemini-deep-research Research the latest developments in AI agents
   ```

2. **Grounding:**
   ```
   /skill gemini-grounding What's the current Bitcoin price?
   ```

3. **Thinking:**
   ```
   /skill gemini-thinking Analyze pros and cons of serverless architecture
   ```

---

### 5.6 Verify Circuit Breaker

Test circuit breaker by forcing failures:

```bash
# Check circuit status
curl $BASE_URL/api/circuits | jq '.gemini_api'

# Should show:
# {
#   "name": "gemini_api",
#   "state": "closed",
#   "failures": 0,
#   ...
# }
```

---

## Rollback Plan

If deployment fails:

```bash
# Rollback to previous version
modal app rollback claude-agents

# Or redeploy without Gemini changes
git checkout HEAD~1 -- agents/main.py
modal deploy agents/main.py
```

---

## Success Criteria

- [ ] `modal deploy` completes without errors
- [ ] `/health` returns OK with gemini_api circuit
- [ ] `/api/skills` lists all 4 Gemini skills
- [ ] `test_gemini` runs successfully
- [ ] `test_grounding` returns answer with citations
- [ ] `test_deep_research` returns report
- [ ] API tests return success responses
- [ ] Telegram commands work with progress updates
- [ ] Circuit breaker shows "closed" state

---

## Post-Deploy Monitoring

```bash
# Watch logs for Gemini calls
modal app logs claude-agents --follow | grep -i gemini

# Check for errors
modal app logs claude-agents --limit 100 | grep -i error
```

---

## Documentation Update

After successful deployment, update:
- `CLAUDE.md` - Add gemini_circuit to list
- `docs/system-architecture.md` - Add Gemini integration
- `docs/deployment-guide.md` - Add GCP secrets setup
