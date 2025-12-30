# Brainstorm: Telegram UX Enhancement for Casual Users

**Date:** Dec 30, 2025
**Status:** Complete
**Target:** Casual users with conversational UX style

---

## Problem Statement

Current Telegram bot UX issues:
1. **Confusing onboarding** - New users don't understand capabilities
2. **Command-heavy** - 15+ commands overwhelming for casual users
3. **No conversation state** - Bot forgets context mid-task
4. **Passive experience** - Users must know what to ask

User requirements:
- Conversational > commands (progressive disclosure)
- Intelligence first (intent detection, FSM, suggestions, personalization)
- Full state tracking (idle, processing, awaiting_input, in_flow)
- Hybrid intent detection (semantic first, LLM for ambiguous)

---

## Current Architecture Analysis

### Existing Strengths
| Component | Status | Notes |
|-----------|--------|-------|
| Intent detection | `src/core/intent.py` | Hybrid keyword + LLM |
| Skill routing | `src/core/router.py` | Qdrant semantic search |
| Personalization | `src/services/user_profile.py` | Profiles, context, macros |
| FAQ system | `src/core/faq.py` | Hybrid keyword + semantic |
| Activity tracking | `src/services/activity.py` | Pattern analysis in Qdrant |
| Suggestions | `src/core/suggestions.py` | Proactive recommendations |

### Gaps to Fill
| Gap | Priority | Effort |
|-----|----------|--------|
| Conversation FSM | High | Medium |
| Smart onboarding | High | Low |
| Status messages | High | Low |
| Quick reply buttons | Medium | Low |
| Response personalization | Medium | Medium |
| Proactive suggestions trigger | Medium | Low |
| Video notes onboarding | Low | High |
| Mini Apps | Low | Very High |

---

## Recommended Solutions

### Phase 1: Conversational Intelligence (Priority)

#### 1.1 Conversation FSM (`src/core/conversation_fsm.py`)

```python
ConversationState = Literal[
    "onboarding",     # First-time user, guided intro
    "idle",           # Ready for new request
    "processing",     # Skill/LLM running
    "awaiting_input", # Bot asked question, waiting reply
    "in_flow",        # Multi-step workflow active
]

class ConversationFSM:
    """Track and manage conversation state per user."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.state: ConversationState = "idle"
        self.context: dict = {}  # Flow-specific data
        self.pending_action: Optional[str] = None
        self.step: int = 0

    def transition(self, event: str) -> ConversationState:
        """State machine transitions."""
        transitions = {
            ("idle", "start_skill"): "processing",
            ("idle", "ask_user"): "awaiting_input",
            ("processing", "complete"): "idle",
            ("processing", "need_input"): "awaiting_input",
            ("awaiting_input", "user_replied"): "processing",
            ("awaiting_input", "cancel"): "idle",
            ("in_flow", "step_complete"): "in_flow",
            ("in_flow", "flow_complete"): "idle",
        }
        new_state = transitions.get((self.state, event), self.state)
        self.state = new_state
        return new_state
```

**Storage:** L1 cache (volatile) + StateManager (persistent)
**Integration:** Wrap `handle_message()` in FSM check

#### 1.2 Enhanced Intent Detection

Extend `src/core/intent.py` with:

```python
# New: Extract skill + parameters in one pass
INTENT_WITH_PARAMS_PROMPT = """Classify and extract from this message:

Message: {message}

Return JSON:
{
  "intent": "chat|skill|orchestrate",
  "skill": "skill-name or null",
  "params": {"key": "value"} or {},
  "confidence": 0.0-1.0
}

Skills available: {skill_list}
"""

async def detect_intent_with_params(message: str) -> IntentResult:
    """One-shot intent + skill + params extraction."""
    # Semantic match first (fast, cheap)
    semantic_match = await semantic_skill_match(message)
    if semantic_match and semantic_match.score > 0.8:
        return IntentResult(
            intent="skill",
            skill=semantic_match.skill_name,
            params=extract_params(message, semantic_match),
            confidence=semantic_match.score
        )

    # LLM for ambiguous cases
    return await llm_classify_with_params(message)
```

#### 1.3 Status Messages (Quick Win)

Add typing indicators and status updates:

```python
async def process_with_status(chat_id: int, message: str):
    """Process message with real-time status updates."""

    # Send typing indicator
    await send_chat_action(chat_id, "typing")

    # Send initial status
    status_msg_id = await send_message(chat_id, "🔄 Processing...")

    intent = await detect_intent(message)

    if intent.intent == "skill":
        await edit_message(chat_id, status_msg_id,
            f"🔍 Running {intent.skill}...")
        result = await execute_skill(intent.skill, message)

    elif intent.intent == "orchestrate":
        await edit_message(chat_id, status_msg_id,
            "🧠 Planning approach...")
        # ... orchestration

    # Delete status message before final response
    await delete_message(chat_id, status_msg_id)
    return result
```

### Phase 2: Smart Onboarding

#### 2.1 First-Time User Detection

```python
async def handle_new_user(chat_id: int, user: dict):
    """Interactive welcome for first-time users."""

    welcome = """👋 Welcome! I'm your AI assistant with 55+ skills.

**What I can do:**
• 🔍 Research any topic deeply
• 💻 Write and review code
• 🎨 Create designs and images
• 📄 Generate documents (PDF, DOCX, PPTX)
• 🌐 Search the web and analyze websites

**Just chat naturally!** No commands needed.

Examples:
• "Research quantum computing trends"
• "Help me plan a new feature"
• "Create a poster for my event"
"""

    keyboard = [
        [{"text": "🔍 Try Research", "callback_data": "demo:research"}],
        [{"text": "💻 Try Coding", "callback_data": "demo:code"}],
        [{"text": "📖 See All Skills", "callback_data": "cat:main"}],
    ]

    await send_telegram_keyboard(chat_id, welcome, keyboard)

    # Set FSM to onboarding
    fsm = get_fsm(chat_id)
    fsm.state = "onboarding"
```

#### 2.2 Contextual Hints

```python
HINTS = {
    "after_error": "💡 Tip: Try rephrasing or use /skills to find the right skill",
    "long_wait": "⏳ This is taking a while. Complex tasks may need 30-60s",
    "first_skill": "✨ Great! You just used your first skill. Try another?",
    "idle_5min": "👋 Still here! Ask me anything or type /suggest for ideas",
}

async def maybe_show_hint(chat_id: int, context: str):
    """Show contextual hint if relevant."""
    hint = HINTS.get(context)
    if hint and should_show_hint(chat_id, context):
        await send_message(chat_id, hint)
        mark_hint_shown(chat_id, context)
```

### Phase 3: Personalized Responses

#### 3.1 Leverage Existing Profile System

Already have: `get_profile()`, `tone`, `response_length`, `domain`, `tech_stack`

Enhancement - inject into system prompt:

```python
async def build_personalized_prompt(user_id: str, base_prompt: str) -> str:
    """Inject user preferences into system prompt."""
    profile = await get_profile(user_id)

    if not profile:
        return base_prompt

    tone = profile.get("tone", "balanced")
    length = profile.get("response_length", "balanced")
    domain = profile.get("domain", "general")

    personalization = f"""
User preferences:
- Tone: {tone} (casual/balanced/formal)
- Length: {length} (concise/balanced/detailed)
- Domain: {domain}

Adapt your response style accordingly.
"""
    return f"{base_prompt}\n\n{personalization}"
```

#### 3.2 Proactive Suggestions Trigger

Currently: `/suggest` command only

Enhancement - auto-trigger after:
- Error recovery
- Long idle periods (>10min)
- Skill completion (contextual follow-up)
- Pattern detection (user often does X after Y)

```python
async def maybe_suggest(chat_id: int, trigger: str):
    """Auto-trigger suggestions when relevant."""
    TRIGGER_CONDITIONS = {
        "after_skill": lambda ctx: ctx.get("skill_success") and random() < 0.3,
        "after_error": lambda ctx: ctx.get("error_count", 0) > 1,
        "idle_long": lambda ctx: ctx.get("idle_minutes", 0) > 10,
    }

    if TRIGGER_CONDITIONS.get(trigger, lambda _: False)(get_context(chat_id)):
        suggestions = await generate_suggestions(chat_id)
        if suggestions:
            keyboard = [[{"text": s, "callback_data": f"suggest:{s}"}]
                       for s in suggestions[:3]]
            await send_telegram_keyboard(
                chat_id,
                "💡 You might want to try:",
                keyboard
            )
```

### Phase 4: Quick Replies (Low Effort, High Impact)

After every response, offer contextual follow-up actions:

```python
def build_quick_replies(context: dict) -> list:
    """Build contextual quick reply buttons."""
    replies = []

    if context.get("skill") == "gemini-deep-research":
        replies = [
            {"text": "📥 Download PDF", "callback_data": "action:download_report"},
            {"text": "🔄 Dig Deeper", "callback_data": "action:research_more"},
            {"text": "📧 Share", "callback_data": "action:share"},
        ]

    elif context.get("skill") == "code-review":
        replies = [
            {"text": "🔧 Apply Fixes", "callback_data": "action:apply_fixes"},
            {"text": "📝 Explain More", "callback_data": "action:explain"},
        ]

    elif context.get("type") == "question":
        replies = [
            {"text": "🔍 Search More", "callback_data": "action:search"},
            {"text": "📚 Related Topics", "callback_data": "action:related"},
        ]

    return [replies] if replies else []
```

---

## Implementation Priority

| Feature | Effort | Impact | Priority |
|---------|--------|--------|----------|
| Status messages | Low | High | P0 |
| Smart onboarding | Low | High | P0 |
| Conversation FSM | Medium | High | P1 |
| Intent + params | Medium | High | P1 |
| Quick replies | Low | Medium | P2 |
| Proactive suggestions | Low | Medium | P2 |
| Response personalization | Medium | Medium | P2 |
| Contextual hints | Low | Low | P3 |

---

## Technical Considerations

### Integration Points
1. `main.py:telegram_webhook()` - FSM state check
2. `main.py:handle_message()` - Status messages
3. `src/core/intent.py` - Enhanced detection
4. `src/core/state.py` - FSM storage
5. `src/services/telegram.py` - Quick reply builders

### Risks
| Risk | Mitigation |
|------|------------|
| Status message rate limits | Telegram allows 30 edits/min, batch updates |
| FSM complexity | Keep states minimal (5 states), test thoroughly |
| LLM cost for intent | Semantic first, LLM only for <70% confidence |
| Onboarding annoyance | One-time only, skip button available |

### Success Metrics
| Metric | Current | Target |
|--------|---------|--------|
| First-message success rate | Unknown | >80% |
| Command usage ratio | High | <20% |
| User retention (7-day) | Unknown | >40% |
| Avg messages per session | Unknown | 5+ |

---

## Not Recommended (Yet)

1. **Mini Apps** - Overkill for current feature set, high dev cost
2. **Video Notes** - Nice-to-have for premium, not MVP
3. **Telegram Stars** - No paid features currently
4. **Reaction Tracking** - Low value for casual users

---

## Next Steps

1. **Immediate:** Implement P0 features (status messages, onboarding)
2. **Week 1:** Build FSM and enhanced intent detection
3. **Week 2:** Add quick replies and proactive suggestions
4. **Week 3:** Test with real users, iterate

---

## Unresolved Questions

1. **FSM persistence** - L1 cache only (lose on restart) or L2 Firebase (more reliable)?
2. **Hint frequency** - How often to show contextual hints before becoming annoying?
3. **Intent confidence threshold** - What score triggers LLM fallback (0.6? 0.7?)?
4. **Quick reply expiry** - Should buttons expire after X minutes?
