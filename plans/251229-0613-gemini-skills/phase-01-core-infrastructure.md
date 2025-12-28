# Phase 1: Core Infrastructure

**Status:** Pending
**Files:** `src/core/resilience.py`, `src/services/gemini.py`

---

## Tasks

### 1.1 Add Gemini Circuit Breaker

**File:** `agents/src/core/resilience.py`

**Changes:**
1. Add after line 224:
```python
gemini_circuit = CircuitBreaker("gemini_api", threshold=3, cooldown=60)
```

2. Update `get_circuit_stats()` (line 227-236):
```python
def get_circuit_stats() -> Dict[str, Dict]:
    """Get stats for all circuits."""
    return {
        "exa_api": exa_circuit.get_stats(),
        "tavily_api": tavily_circuit.get_stats(),
        "firebase": firebase_circuit.get_stats(),
        "qdrant": qdrant_circuit.get_stats(),
        "claude_api": claude_circuit.get_stats(),
        "telegram_api": telegram_circuit.get_stats(),
        "gemini_api": gemini_circuit.get_stats(),  # NEW
    }
```

3. Update `reset_all_circuits()` (line 239-247):
```python
def reset_all_circuits():
    """Reset all circuits (for testing/recovery)."""
    exa_circuit.reset()
    tavily_circuit.reset()
    firebase_circuit.reset()
    qdrant_circuit.reset()
    claude_circuit.reset()
    telegram_circuit.reset()
    gemini_circuit.reset()  # NEW
```

---

### 1.2 Create GeminiClient

**File:** `agents/src/services/gemini.py` (NEW)

See `plan.md` Phase 1.2 for full implementation.

**Key classes:**
- `GroundedResponse` - dataclass for grounded answers
- `ResearchReport` - dataclass for deep research output
- `GeminiClient` - main client with methods:
  - `chat()` - standard chat with thinking levels
  - `grounded_query()` - factual queries with citations
  - `deep_research()` - agentic multi-step research
  - `analyze_image()` - vision analysis

**Dependencies:**
```bash
pip install google-genai
```

---

### 1.3 Update Modal Image

**File:** `agents/main.py`

Find image definition and add:
```python
image = modal.Image.debian_slim().pip_install(
    # ... existing deps
    "google-genai",  # NEW: Vertex AI Gemini SDK
)
```

---

### 1.4 Add GCP Secrets

**Action:** Run locally:
```bash
modal secret create gcp-credentials \
  GCP_PROJECT_ID=your-project-id \
  GCP_LOCATION=us-central1 \
  GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'
```

**Then update main.py app secrets:**
```python
app = modal.App(
    "claude-agents",
    secrets=[
        # ... existing secrets
        modal.Secret.from_name("gcp-credentials"),  # NEW
    ],
)
```

---

## Validation

```bash
# Test GeminiClient initialization
python3 -c "
from agents.src.services.gemini import get_gemini_client
client = get_gemini_client()
print(f'Project: {client.project_id}')
print(f'Location: {client.location}')
"

# Test circuit breaker
python3 -c "
from agents.src.core.resilience import gemini_circuit, get_circuit_stats
print(gemini_circuit.get_stats())
"
```

---

## Completion Criteria

- [ ] `gemini_circuit` exists in resilience.py
- [ ] `get_circuit_stats()` includes gemini
- [ ] `reset_all_circuits()` includes gemini
- [ ] `GeminiClient` class created with all methods
- [ ] `google-genai` added to Modal image
- [ ] GCP secrets configured in Modal
