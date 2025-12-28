# Phase 2B: Core Orchestrator Fix

## Files
- `agents/src/core/orchestrator.py`

## Issues

### 1. Missing DAG Validation (HIGH)
**File:** orchestrator.py
**Problem:** Cyclic dependencies cause silent failures
**Fix:** Add topological sort validation

```python
def _validate_dag(self, skills: List[str], dependencies: Dict[str, List[int]]) -> bool:
    """Validate skill dependencies form a DAG (no cycles)."""
    n = len(skills)
    visited = [0] * n  # 0=unvisited, 1=visiting, 2=visited

    def has_cycle(node: int) -> bool:
        if visited[node] == 1:
            return True  # Back edge = cycle
        if visited[node] == 2:
            return False

        visited[node] = 1
        for dep in dependencies.get(skills[node], []):
            if dep < n and has_cycle(dep):
                return True

        visited[node] = 2
        return False

    for i in range(n):
        if visited[i] == 0 and has_cycle(i):
            self.logger.error("dag_cycle_detected", skills=skills)
            return False

    return True

async def execute(self, task: str, context: dict) -> str:
    # Parse skills and dependencies from LLM
    plan = await self._create_plan(task, context)

    # Validate DAG before execution
    if not self._validate_dag(plan.skills, plan.dependencies):
        return "Error: Circular skill dependency detected"

    # Continue with execution...
```

### 2. LLM Output Validation
**Problem:** LLM can return invalid dependency indices
**Fix:** Validate indices before use

```python
def _validate_dependencies(self, skills: List[str], deps: Dict[str, List[int]]) -> Dict[str, List[int]]:
    """Validate and sanitize dependency indices."""
    n = len(skills)
    validated = {}

    for skill, indices in deps.items():
        valid_indices = [i for i in indices if 0 <= i < n and skills[i] != skill]
        validated[skill] = valid_indices

    return validated
```

## Success Criteria
- [x] Cyclic dependencies detected and rejected
- [x] Invalid indices handled gracefully
- [x] Clear error messages for users

## Implementation Status

**COMPLETED** - 2025-12-28

### Changes Made

1. **Added `_validate_dependencies` method** (lines 125-160)
   - Validates and sanitizes dependency indices
   - Removes out-of-bounds indices (< 0 or >= n)
   - Removes self-references (skill depends on itself)
   - Logs warnings when invalid dependencies removed

2. **Added `_validate_dag` method** (lines 162-213)
   - Implements DFS with three-color marking
   - Detects cycles using back-edge detection
   - Handles disconnected components
   - Logs error with cycle path when detected

3. **Updated `execute` method** (lines 71-123)
   - Step 2: Validate and sanitize dependencies
   - Step 3: Validate DAG (no cycles)
   - Returns clear error if cycle detected
   - Updated step numbering (now 6 steps total)

### Test Results

Created test suite: `agents/test_dag_validation.py`

```
✓ Valid linear DAG passes
✓ Cycle detected correctly
✓ Self-references removed
✓ Out-of-bounds indices removed
✓ Complex DAG (diamond) passes

✓ All tests passed!
```

### Files Modified
- `/Users/nad/Library/CloudStorage/OneDrive-Personal/Agents/agents/src/core/orchestrator.py` (+91 lines)
