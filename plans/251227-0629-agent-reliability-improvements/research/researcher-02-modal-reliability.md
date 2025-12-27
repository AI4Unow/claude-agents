# Modal.com Reliability Features Research

## Overview

Modal emphasizes "fail-fast and retry" architecture with granular control over failures, timeouts, and preemptions.

## 1. Retry Mechanisms

### Infrastructure vs Application Errors
- **Infrastructure** (container crashes): Auto-retry with crash-loop backoff
- **Application** (transient errors): Developer-configured retries

### Simple Retries
```python
@app.function(retries=3)  # Fixed 1-second delay
def my_function():
    ...
```

### Advanced Retries (Exponential Backoff)
```python
from modal import Retries

@app.function(
    retries=Retries(
        max_retries=5,
        backoff_coefficient=2.0,
        initial_delay=1.0,
    )
)
def my_function():
    ...
```

### Best Practice: Idempotency
- Functions may be retried or moved to different containers
- Side effects (DB writes) must be safe to repeat
- Use unique task IDs for deduplication

## 2. Timeout Configuration

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `timeout` | 300s | 1s - 24h | Per execution attempt |
| `startup_timeout` | - | - | For loading models/data |
| Web endpoints | 150s | - | Use async for longer |

### Timeout per Attempt
- 3 retries + 60s timeout = 180s total potential
- Each retry resets the timeout clock

### Web Endpoint Strategy
- For tasks >150s: Use internal `modal.call`
- Or implement polling mechanism

## 3. Preemption Handling

Modal uses spot instances for cost efficiency.

### Non-Preemptible Functions
```python
@app.function(nonpreemptible=True)  # 3x cost
def critical_task():
    ...
```

### SIGINT Handling
- Container receives SIGINT before preemption
- Catch signal for cleanup/checkpointing

### Checkpointing Strategy
```python
import signal

def save_checkpoint():
    volume.commit()

signal.signal(signal.SIGINT, lambda s, f: save_checkpoint())
```

## 4. Error Handling

### Timeout Exceptions
```python
from modal.exception import FunctionTimeoutError

try:
    result = long_task.remote()
except FunctionTimeoutError:
    # Fallback logic
    pass
```

### Rate Limit Handling
- Modal client auto-handles 429 errors
- Tune via `MODAL_MAX_THROTTLE_WAIT` env var

## 5. Volume Reliability

### Commit Strategy
- Always `volume.commit()` after writes
- Uncommitted changes lost on container restart

### Concurrent Access
- Multiple containers can read simultaneously
- Writes require coordination (use locks or single-writer)

## Recommendations for II Framework

1. **Add Retries to All Functions**
   ```python
   @app.function(
       retries=Retries(max_retries=3, backoff_coefficient=2.0),
       timeout=300,
   )
   ```

2. **Implement Checkpointing**
   - Save agent state to Volume periodically
   - Resume from checkpoint on restart

3. **Handle Preemption**
   - Register SIGINT handler
   - Commit Volume before shutdown

4. **Make Operations Idempotent**
   - Use task IDs in Firebase
   - Check for existing results before processing

5. **Add Health Checks**
   - `/health` endpoint for Telegram agent
   - Monitor via external service

## Sources

- [Modal Docs: Retries & Timeouts](https://modal.com/docs/guide/retries)
- [Modal Reference: Function Decorators](https://modal.com/docs/reference/modal.App#function)
- [Modal Blog: Idempotency](https://modal.com/blog/idempotency)
