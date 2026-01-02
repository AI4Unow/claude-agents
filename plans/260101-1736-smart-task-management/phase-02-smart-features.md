# Phase 2: Smart Features

## Context
- **Parent Plan**: [plan.md](plan.md)
- **Dependencies**: [Phase 0: SDK Foundation](phase-00-sdk-foundation.md), [Phase 1: Core Foundation](phase-01-core-foundation.md)
- **Research**: [NLP Parsing](research/researcher-nlp-parsing.md)

## Overview
| Field | Value |
|-------|-------|
| Date | 2026-01-01 |
| Priority | P1 |
| Effort | 8h |
| Status | pending |

Build intelligent features: smart timing engine, task extraction from conversations, auto-reschedule on conflicts, and completion verification.

## Key Insights (from Research)

1. **Learning signals**: Completion time patterns, snooze frequency, procrastination patterns
2. **Task extraction**: Detect actionable items in regular conversation
3. **Auto-reschedule**: Use calendar gaps + priority to find optimal times
4. **Completion verification**: Some tasks verifiable (meetings, API calls)

## Requirements

1. Smart timing engine learns optimal reminder times
2. Extract tasks from natural conversations (with confidence score)
3. Auto-reschedule tasks when calendar conflicts detected
4. Verify certain task completions programmatically
5. All smart actions follow trust rules from Phase 1

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PHASE 2 ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐                                                    │
│  │  Smart Timing    │◄─────────────────────────────────────┐            │
│  │    Engine        │                                       │            │
│  │                  │     Learning Signals:                 │            │
│  │ • Priority weight│     • Completion patterns             │            │
│  │ • Energy match   │     • Snooze frequency                │            │
│  │ • Calendar gaps  │     • Calendar density                │            │
│  │ • Historical data│     • Context availability            │            │
│  └────────┬─────────┘                                       │            │
│           │                                                  │            │
│           ▼                                                  │            │
│  ┌──────────────────┐     ┌──────────────────┐     ┌───────┴────────┐  │
│  │ Task Extraction  │────►│ Auto-Reschedule  │────►│ Completion     │  │
│  │                  │     │                  │     │ Verification   │  │
│  │ Conversation     │     │ Conflict detect  │     │                │  │
│  │ → Actionable     │     │ Find optimal slot│     │ • Meeting held │  │
│  │ items w/score    │     │ Trust rules      │     │ • API callback │  │
│  └──────────────────┘     └──────────────────┘     │ • Location     │  │
│                                                     └────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Related Files

| File | Action | Purpose |
|------|--------|---------|
| `src/core/smart_timing.py` | Create | Timing optimization engine |
| `src/core/task_extractor.py` | Create | Extract tasks from conversations |
| `src/core/auto_scheduler.py` | Create | Conflict detection and reschedule |
| `src/core/completion_verifier.py` | Create | Programmatic task verification |
| `src/services/agentic.py` | Modify | Integrate extraction in message flow |
| `src/services/firebase/user_activity.py` | Create | Store learning signals |

## Implementation Steps

### 1. Smart Timing Engine (3h)

1.1. Create `src/core/smart_timing.py`:
```python
@dataclass
class TimingFactors:
    task_priority: float  # 0.0-1.0
    estimated_duration: int  # minutes
    energy_match: float  # 0.0-1.0
    calendar_gap_score: float  # 0.0-1.0
    historical_completion_score: float  # 0.0-1.0
    context_availability: float  # 0.0-1.0

class SmartTimingEngine:
    """Learn optimal reminder times from user behavior."""

    async def calculate_optimal_time(
        self,
        task: SmartTask,
        user_id: int,
        calendar_events: List[Dict]
    ) -> datetime:
        """Find best reminder time based on learned patterns."""

        # Load user activity data
        activity = await self._get_user_activity(user_id)

        factors = TimingFactors(
            task_priority=self._priority_weight(task.priority),
            estimated_duration=task.estimated_duration or 30,
            energy_match=self._match_energy_to_time(task.energy_level, activity),
            calendar_gap_score=self._find_gap_score(calendar_events, task.due_date),
            historical_completion_score=self._completion_patterns(activity, task),
            context_availability=self._context_windows(task.context, activity)
        )

        return self._optimize(factors, task.due_date)

    def _priority_weight(self, priority: Optional[str]) -> float:
        weights = {"p1": 1.0, "p2": 0.75, "p3": 0.5, "p4": 0.25}
        return weights.get(priority, 0.5)

    def _match_energy_to_time(
        self,
        energy: Optional[str],
        activity: UserActivity
    ) -> float:
        """Match task energy to user's typical energy patterns by hour."""
        # High energy tasks → morning for most users
        # Low energy → afternoon slump times
        if not energy or not activity.energy_patterns:
            return 0.5

        # activity.energy_patterns = {hour: avg_completion_rate}
        best_hour = max(activity.energy_patterns, key=activity.energy_patterns.get)
        return activity.energy_patterns.get(best_hour, 0.5)

    def _find_gap_score(
        self,
        events: List[Dict],
        target_date: Optional[datetime]
    ) -> float:
        """Score based on calendar free time around target."""
        if not target_date or not events:
            return 0.5

        # Find gaps before due_date
        gaps = self._calculate_gaps(events, target_date)
        if not gaps:
            return 0.2  # No good gaps
        return min(1.0, max(gaps) / 60)  # Normalize by 1 hour

    async def record_completion(
        self,
        task: SmartTask,
        completed_at: datetime
    ) -> None:
        """Record completion for learning."""
        await self._store_signal(
            user_id=task.user_id,
            signal_type="completion",
            task_type=task.type,
            hour=completed_at.hour,
            day_of_week=completed_at.weekday(),
            priority=task.priority,
            context=task.context
        )
```

1.2. Learning signals storage:
```python
@dataclass
class UserActivity:
    user_id: int
    energy_patterns: Dict[int, float]  # hour → completion rate
    completion_by_day: Dict[int, int]  # weekday → count
    snooze_count: int
    avg_procrastination_hours: float
    context_times: Dict[str, List[int]]  # context → preferred hours
```

### 2. Task Extraction from Conversations (2h)

2.1. Create `src/core/task_extractor.py`:
```python
@dataclass
class ExtractedTask:
    content: str
    confidence: float  # 0.0-1.0
    source_text: str
    trigger_words: List[str]

class TaskExtractor:
    """Extract actionable tasks from natural conversation."""

    TRIGGER_PATTERNS = [
        r"(?:I |we )?(?:need to|have to|should|must|gotta) (.+)",
        r"(?:don't forget to|remember to) (.+)",
        r"(?:remind me to|remind me about) (.+)",
        r"(?:I'll|i'll) (.+) (?:later|tomorrow|next|soon)",
        r"(?:todo|to do|to-do):?\s*(.+)",
    ]

    EXCLUSION_PATTERNS = [
        r"(?:I think|maybe|perhaps|possibly)",
        r"(?:would be nice|could)",
        r"\?$",  # Questions not tasks
    ]

    async def extract_from_message(
        self,
        message: str,
        current_time: datetime
    ) -> List[ExtractedTask]:
        """Extract potential tasks from conversational message."""

        # Quick pattern match first
        pattern_matches = self._pattern_extract(message)

        # If patterns found, validate with LLM
        if pattern_matches:
            validated = await self._llm_validate(pattern_matches, message)
            return [t for t in validated if t.confidence >= 0.7]

        # No patterns but might be implicit task
        if self._might_be_task(message):
            llm_extract = await self._llm_extract(message, current_time)
            return [t for t in llm_extract if t.confidence >= 0.8]

        return []

    def _pattern_extract(self, message: str) -> List[str]:
        """Fast regex extraction of potential tasks."""
        matches = []
        for pattern in self.TRIGGER_PATTERNS:
            for match in re.finditer(pattern, message, re.IGNORECASE):
                candidate = match.group(1).strip()
                if not self._should_exclude(candidate):
                    matches.append(candidate)
        return matches

    def _should_exclude(self, text: str) -> bool:
        """Check exclusion patterns."""
        for pattern in self.EXCLUSION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    async def _llm_validate(
        self,
        candidates: List[str],
        context: str
    ) -> List[ExtractedTask]:
        """LLM validates and scores extracted candidates."""
        prompt = f"""
Validate these potential tasks extracted from conversation:
Context: "{context}"

Candidates:
{chr(10).join(f"- {c}" for c in candidates)}

For each, return:
- is_actionable: true/false
- confidence: 0.0-1.0
- cleaned_task: refined task description
"""
        # Call LLM and parse response
        ...
```

2.2. Integration with agentic loop:
```python
# In agentic.py message handler
extracted = await task_extractor.extract_from_message(user_message, now)
for task in extracted:
    action = AgentAction(
        type="task_extraction",
        payload={"content": task.content, "confidence": task.confidence}
    )
    await action_pipeline.propose_action(user_id, action, trust_engine)
```

### 3. Auto-Reschedule on Conflicts (2h)

3.1. Create `src/core/auto_scheduler.py`:
```python
@dataclass
class ConflictInfo:
    task_id: str
    conflict_type: Literal["overlap", "too_close", "no_time"]
    conflicting_event: Optional[Dict]
    suggested_times: List[datetime]

class AutoScheduler:
    """Detect calendar conflicts and suggest/apply reschedules."""

    MIN_GAP_MINUTES = 15  # Buffer between events
    LOOKAHEAD_DAYS = 7

    async def check_conflicts(
        self,
        task: SmartTask,
        calendar_events: List[Dict]
    ) -> Optional[ConflictInfo]:
        """Check if task time conflicts with calendar."""

        if not task.due_date or not task.due_time:
            return None

        task_start = datetime.combine(task.due_date, task.due_time)
        task_end = task_start + timedelta(minutes=task.estimated_duration or 30)

        for event in calendar_events:
            event_start = event["start"]
            event_end = event["end"]

            # Check overlap
            if self._overlaps(task_start, task_end, event_start, event_end):
                suggestions = await self._find_alternatives(
                    task, calendar_events, task_start
                )
                return ConflictInfo(
                    task_id=task.id,
                    conflict_type="overlap",
                    conflicting_event=event,
                    suggested_times=suggestions[:3]
                )

        return None

    async def auto_reschedule(
        self,
        task: SmartTask,
        conflict: ConflictInfo,
        trust_engine: TrustRulesEngine
    ) -> bool:
        """Reschedule task if trust rules allow."""

        action_type = "work_reschedule" if task.context == "@work" else "personal_changes"

        if not conflict.suggested_times:
            return False

        if trust_engine.should_auto_execute(action_type):
            # Apply first suggestion
            new_time = conflict.suggested_times[0]
            await update_task(task.user_id, task.id, due_date=new_time.date(), due_time=new_time.time())

            if trust_engine.should_notify(action_type):
                await notify_reschedule(task.user_id, task, new_time, conflict.conflicting_event)

            return True
        else:
            # Queue for confirmation
            await queue_reschedule_confirmation(task, conflict.suggested_times)
            return False

    def _overlaps(
        self,
        start1: datetime, end1: datetime,
        start2: datetime, end2: datetime
    ) -> bool:
        """Check if two time ranges overlap."""
        buffer = timedelta(minutes=self.MIN_GAP_MINUTES)
        return not (end1 + buffer <= start2 or end2 + buffer <= start1)
```

### 4. Completion Verification (1h)

4.1. Create `src/core/completion_verifier.py`:
```python
class CompletionVerifier:
    """Verify task completion programmatically where possible."""

    VERIFIABLE_PATTERNS = {
        "meeting": r"(?:meet|call|sync|standup|1:1)",
        "email": r"(?:email|mail|send to)",
        "api_call": r"(?:deploy|push|merge|release)",
        "location": r"(?:go to|visit|pick up from|drop off at)",
    }

    async def can_verify(self, task: SmartTask) -> Optional[str]:
        """Check if task can be auto-verified. Returns verification type."""
        for vtype, pattern in self.VERIFIABLE_PATTERNS.items():
            if re.search(pattern, task.content, re.IGNORECASE):
                return vtype
        return None

    async def verify(
        self,
        task: SmartTask,
        verification_type: str,
        context: Dict
    ) -> bool:
        """Attempt to verify task completion."""

        if verification_type == "meeting":
            # Check if calendar event with matching title exists and ended
            return await self._verify_meeting_held(task, context.get("calendar_events", []))

        elif verification_type == "email":
            # Would need email API integration
            return False  # Not implemented yet

        elif verification_type == "api_call":
            # Check deployment status, PR merged, etc.
            return await self._verify_api_action(task, context)

        elif verification_type == "location":
            # Would need location API
            return False  # Not implemented yet

        return False

    async def _verify_meeting_held(
        self,
        task: SmartTask,
        calendar_events: List[Dict]
    ) -> bool:
        """Check if meeting occurred based on calendar."""
        now = datetime.now(timezone.utc)

        # Extract meeting keywords from task
        keywords = self._extract_keywords(task.content)

        for event in calendar_events:
            if event["end"] < now:  # Event has ended
                if any(kw.lower() in event.get("summary", "").lower() for kw in keywords):
                    return True

        return False
```

## Todo List

- [ ] Create SmartTimingEngine class
- [ ] Implement learning signal storage (UserActivity)
- [ ] Build priority/energy/calendar gap scoring
- [ ] Create TaskExtractor with pattern matching
- [ ] Add LLM validation for extracted tasks
- [ ] Integrate extraction in agentic loop
- [ ] Build AutoScheduler conflict detection
- [ ] Implement reschedule with trust rules
- [ ] Create CompletionVerifier for meetings
- [ ] Add notification templates for all actions
- [ ] Write tests for timing optimization
- [ ] Write tests for task extraction accuracy

## Success Criteria

1. Smart timing suggests times within user's active hours 95%+ of time
2. Task extraction precision >80% (avoid false positives)
3. Auto-reschedule finds valid alternative 90%+ of conflicts
4. Meeting verification accurate for calendar-linked meetings

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Task extraction false positives | High | Medium | High confidence threshold (0.8+) |
| Learning cold start (no data) | Medium | High | Sensible defaults, quick learning |
| Calendar API rate limits | Medium | Low | Cache, batch requests |
| Verification inaccuracy | Medium | Medium | Mark as "likely complete", confirm |

## Security Considerations

1. Don't store full calendar event details, only timing metadata
2. Task extraction should not process messages marked as private
3. Completion verification should not access third-party APIs without consent
4. Learning data anonymized for any analytics

## Next Steps

After Phase 2 complete:
1. Proceed to [Phase 3: Calendar Sync](phase-03-calendar-sync.md)
2. Collect baseline metrics before enabling smart features
3. A/B test smart timing vs manual timing

## Unresolved Questions

1. How much historical data needed before smart timing is effective?
2. ~~Should task extraction work on group chats or only 1:1?~~ → All groups (validated, needs noise filtering)
3. How to handle false positive extractions gracefully?
4. What's the minimum confidence threshold for auto-creation?
5. How to filter actionable items from casual group chat conversation?
