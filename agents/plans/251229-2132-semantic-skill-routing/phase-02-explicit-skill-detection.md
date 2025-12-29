# Phase 2: Explicit Skill Detection

## Context

- Parent: [plan.md](plan.md)
- Depends on: Phase 1 (intent.py exists)
- Related: [router.py](../../src/core/router.py) - SkillRouter

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P1 |
| Effort | 30min |
| Status | pending |
| Review | pending |

Add detection for explicit `/skill_name` and `@skill_name` invocations. Bypass intent classifier when user explicitly requests skill.

## Key Insights

- Users should be able to invoke skills directly: `/research quantum computing`
- Both `/` and `@` prefixes supported for flexibility
- Fuzzy match skill name against registry for typo tolerance
- Extract remaining text as task/query

## Requirements

1. Regex pattern: `^[/@](\w[\w-]*)\s*(.*)$`
2. Fuzzy match skill name against SkillRegistry.get_names()
3. Return (skill_name, remaining_text) or None if no match
4. Add to router.py as `parse_explicit_skill()`

## Architecture

```python
# In src/core/router.py

EXPLICIT_SKILL_PATTERN = re.compile(r'^[/@]([\w-]+)\s*(.*)$', re.IGNORECASE)

def parse_explicit_skill(message: str, registry: SkillRegistry) -> tuple[str, str] | None:
    """Parse /skill or @skill invocation.

    Returns:
        (skill_name, remaining_text) or None if no match
    """
    match = EXPLICIT_SKILL_PATTERN.match(message.strip())
    if not match:
        return None

    skill_query = match.group(1).lower()
    remaining = match.group(2).strip()

    # Exact match first
    skill_names = registry.get_names()
    if skill_query in skill_names:
        return (skill_query, remaining)

    # Fuzzy match (prefix match)
    for name in skill_names:
        if name.startswith(skill_query):
            return (name, remaining)

    return None  # No skill matched
```

## Related Code Files

- `src/core/router.py` - Add parse_explicit_skill()
- `src/skills/registry.py` - SkillRegistry.get_names()
- `main.py` - Will call this before intent classification

## Implementation Steps

1. Add `EXPLICIT_SKILL_PATTERN` regex to router.py
2. Implement `parse_explicit_skill()` function
3. Add prefix fuzzy matching for typo tolerance
4. Return None if no skill matches (falls through to normal flow)

## Todo List

- [ ] Add regex pattern constant
- [ ] Implement parse_explicit_skill()
- [ ] Add fuzzy/prefix matching
- [ ] Test with sample commands

## Success Criteria

- [ ] `/research topic` → ("gemini-deep-research", "topic")
- [ ] `@design poster` → ("canvas-design", "poster")
- [ ] `/unknown xyz` → None (no match)
- [ ] `/res topic` → ("research", "topic") via prefix match

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Skill name collision | Low | Exact match first |
| Typo not caught | Low | Prefix matching helps |
| Wrong skill matched | Medium | Show skill name before exec |

## Security Considerations

- Validate skill exists in registry before execution
- No injection risk - only alphanumeric skill names

## Next Steps

After Phase 2 complete → Phase 3: Auto Mode Routing Update
