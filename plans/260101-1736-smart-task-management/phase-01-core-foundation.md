# Phase 1: Core Foundation

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: [Phase 0: SDK Foundation](phase-00-sdk-foundation.md)
- **Research**: [NLP Parsing](research/researcher-nlp-parsing.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2026-01-01 |
| Priority | P1 |
| Effort | 7h |
| Status | pending |

Unify `reminders.py` into `pkm.py` with enhanced `SmartTask` model. Build hybrid NLP parser. (Trust rules and action pipeline now handled by SDK in Phase 0.)

## Key Insights (from Research)

1. **LLM + dateparser hybrid**: LLM extracts intent + raw time string, dateparser normalizes with `RELATIVE_BASE`
2. **Skip spaCy for MVP**: Entity validation optional, adds latency
3. **`STRICT_PARSING=True`**: Prevents false positive date hallucinations
4. **Include current time in LLM prompt**: Critical for relative time resolution

## Requirements

1. Migrate `reminders.py` functionality into unified `SmartTask` model
2. Hard cutover: Delete `reminders.py` completely (no backward compatibility)
3. Build hybrid NLP parser (LLM + dateparser)
4. SmartTask CRUD via SDK tools (from Phase 0)
5. Add new circuit breaker if external services added

**Note:** Trust rules and undo/action pipeline are now handled by SDK Hooks and Checkpointing (Phase 0).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1 ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User Input                                                              │
│      │                                                                   │
│      ▼                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │  LLM Layer  │────►│  dateparser │────►│  SmartTask  │               │
│  │ (Intent +   │     │ (Normalize) │     │  (Firebase) │               │
│  │  Candidate) │     │             │     │             │               │
│  └─────────────┘     └─────────────┘     └──────┬──────┘               │
│                                                  │                       │
│                                          ┌──────▼──────┐                │
│                                          │  SDK Tools  │                │
│                                          │ (Phase 0)   │                │
│                                          └──────┬──────┘                │
│                                                  │                       │
│                                          ┌──────▼──────┐                │
│                                          │  SDK Hooks  │                │
│                                          │ Trust Rules │                │
│                                          └─────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Files

| File | Action | Purpose |
|------|--------|---------|
| `src/services/firebase/pkm.py` | Modify | Extend PKMItem → SmartTask |
| `src/services/firebase/reminders.py` | Delete | Hard cutover (no backward compat) |
| `src/core/nlp_parser.py` | Create | Hybrid NLP parsing (LLM + dateparser) |
| `src/sdk/tools/task_tools.py` | Modify | Use SmartTask model (from Phase 0) |
| `src/services/firebase/user_settings.py` | Modify | Add task-related settings |

**Note:** `trust_rules.py` and `agent_actions.py` are replaced by SDK Hooks and Checkpointing (see Phase 0).

## Implementation Steps

### 1. SmartTask Model (3h)

1.1. Extend `PKMItem` → `SmartTask` in `pkm.py`:
```python
@dataclass
class SmartTask:
    id: str
    user_id: int
    content: str
    type: Literal["task", "note", "idea", "link", "quote"]
    status: Literal["inbox", "active", "done", "archived"]
    tags: List[str] = field(default_factory=list)
    project: Optional[str] = None
    priority: Optional[Literal["p1", "p2", "p3", "p4"]] = None

    # Time fields (from reminders)
    due_date: Optional[datetime] = None
    due_time: Optional[time] = None
    reminder_offset: Optional[int] = None  # Minutes before due
    recurrence: Optional[str] = None  # RRULE format

    # Smart fields
    estimated_duration: Optional[int] = None  # Minutes
    energy_level: Optional[Literal["high", "medium", "low"]] = None
    context: Optional[str] = None  # @home, @work, @errands
    blocked_by: List[str] = field(default_factory=list)

    # Calendar sync
    google_event_id: Optional[str] = None
    google_task_id: Optional[str] = None
    apple_uid: Optional[str] = None

    # Agent metadata
    auto_created: bool = False
    source_message_id: Optional[int] = None
    confidence_score: Optional[float] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

1.2. Update conversion functions `_item_to_dict()` and `_dict_to_item()`

1.3. Add migration function for existing PKMItems (add missing fields)

1.4. Delete `reminders.py` completely (hard cutover per validation decision)

### 2. Hybrid NLP Parser (4h)

2.1. Create `src/core/nlp_parser.py`:
```python
@dataclass
class ParsedTask:
    content: str
    intent: Literal["task", "reminder", "query"]
    due_date: Optional[datetime] = None
    due_time: Optional[time] = None
    recurrence: Optional[str] = None
    priority: Optional[str] = None
    context: Optional[str] = None
    confidence: float = 1.0
    raw_time_str: Optional[str] = None  # For debugging

async def parse_task(
    user_input: str,
    current_time: datetime,
    timezone: str = "UTC"
) -> ParsedTask:
    """Hybrid parse: LLM for intent, dateparser for time."""

    # Step 1: LLM extraction
    llm_result = await _llm_extract(user_input, current_time)

    # Step 2: dateparser normalization
    if llm_result.raw_time_str:
        parsed_dt = dateparser.parse(
            llm_result.raw_time_str,
            settings={
                'RELATIVE_BASE': current_time,
                'PREFER_DATES_FROM': 'future',
                'STRICT_PARSING': True,
                'TIMEZONE': timezone
            }
        )
        if parsed_dt:
            llm_result.due_date = parsed_dt.date()
            llm_result.due_time = parsed_dt.time() if parsed_dt.time() != time(0,0) else None

    return llm_result
```

2.2. LLM prompt template (include current time):
```
You are a task parser. Current time: {current_time} ({timezone}).
Extract from the user message:
- task_content: The action to do
- time_expression: Raw time string if mentioned (e.g., "tomorrow 3pm", "next Friday")
- priority: p1/p2/p3/p4 if mentioned
- context: @home/@work/@errands if mentioned
- intent: "task" (actionable) or "reminder" (notification only) or "query" (asking about tasks)

User message: "{user_input}"
```

2.3. Handle recurrence patterns:
- Use `dateutil.rrule` to generate RRULE string
- Common patterns: "every Monday", "daily", "weekly"
- Full RRULE support per validation decision

## Todo List

- [ ] Extend PKMItem to SmartTask dataclass
- [ ] Update Firebase conversion functions
- [ ] Delete reminders.py (hard cutover)
- [ ] Create hybrid NLP parser module
- [ ] Build LLM extraction prompt
- [ ] Integrate dateparser with RELATIVE_BASE
- [ ] Implement full RRULE parsing with dateutil.rrule
- [ ] Update SDK task_tools.py to use SmartTask
- [ ] Write unit tests for NLP parser
- [ ] Write integration tests for SmartTask CRUD

**Note:** Trust rules engine and agent action pipeline are now implemented in Phase 0 via SDK Hooks and Checkpointing.

## Success Criteria

1. SmartTask model stores all legacy PKMItem and Reminder fields
2. NLP parser achieves >90% accuracy on test patterns
3. Full RRULE support for complex recurrence patterns
4. reminders.py deleted, no backward compatibility issues
5. SDK tools successfully use SmartTask model

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| dateparser false positives | Medium | Medium | Use STRICT_PARSING, validate output |
| LLM latency for parsing | Medium | Low | Cache common patterns, async execution |
| Migration breaks existing data | High | Low | Add migration script, test on staging |
| Hard cutover breaks users | Medium | Low | Notify users, quick rollback plan |

## Security Considerations

1. User input sanitization before LLM prompt injection
2. Validate SmartTask fields before Firebase storage
3. Log all task operations for audit trail

## Next Steps

After Phase 1 complete:
1. Proceed to [Phase 2: Smart Features](phase-02-smart-features.md)
2. Deploy to staging for testing
3. Collect NLP parsing accuracy metrics

## Unresolved Questions

1. ~~Should RRULE parsing support complex patterns or just common ones?~~ → Full RRULE (validated)
2. How to handle timezone for users who travel?
3. ~~Should undo queue persist across deploys?~~ → SDK Checkpointing handles this (Phase 0)
