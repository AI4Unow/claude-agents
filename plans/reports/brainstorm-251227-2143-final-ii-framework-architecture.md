# Final II Framework Architecture (Context Engineering Aligned)

## Problem Statement

Design a unified memory architecture for the II Framework that:
1. Shares 59 Claude Code skills between local and Modal.com
2. Implements robust memory across sessions
3. Follows context engineering best practices
4. Balances complexity with reliability

## Key Influences

### Context Engineering Principles (from Agent-Skills-for-Context-Engineering)

| Principle | Application |
|-----------|-------------|
| Memory Spectrum | 4-layer architecture: Working → Short-term → Long-term → Semantic |
| Progressive Disclosure | Load skill name/description first, full content on activation |
| Temporal Knowledge Graph | All facts have valid_from/valid_until for time-travel queries |
| Context Compaction | Summarize at 80% context usage |
| Observation Masking | Store verbose outputs, reference in context |
| Source of Truth | Structured DB primary, vector store derived |

### Benchmark Data

| Memory System | Accuracy | Architecture |
|---------------|----------|--------------|
| Temporal KG | 94.8% | Graph + temporal validity |
| Vector RAG alone | 60-70% | Loses relationships |

## Final Architecture

### Memory Spectrum

```
Layer 1: WORKING MEMORY (Context Window)
├── Current skill info.md content
├── Active task state
├── Recent tool outputs (masked if verbose)
└── Retrieved Qdrant matches

Layer 2: SHORT-TERM MEMORY (Modal Volume)
├── info.md ## Memory section
├── Per-session patterns
└── Compacted work summaries

Layer 3: LONG-TERM MEMORY (Firebase - Primary)
├── skills/{id} - config, stats, memory backup
├── entities/{id} - with temporal validity
├── decisions/{id} - learned rules with validity
└── logs/{id} - execution history

Layer 4: SEMANTIC INDEX (Qdrant - Derived)
├── skills collection - semantic skill matching
├── knowledge collection - cross-skill insights
├── errors collection - error pattern matching
└── conversations - chat history
```

### Firebase Schema (Temporal)

```javascript
// skills/{skillId}
{
  name: "planning",
  config: { ... },
  stats: {
    runCount: 42,
    successRate: 0.95,
    lastRun: Timestamp
  },
  memoryBackup: "..." // Backup of info.md ## Memory
}

// entities/{entityId}
{
  type: "user_preference",
  key: "output_format",
  value: "markdown",
  valid_from: Timestamp("2025-01-01"),
  valid_until: null,  // Current
  source_skill: "planning"
}

// decisions/{decisionId}
{
  condition: "user asks for code review",
  action: "activate code-review skill",
  confidence: 0.92,
  learned_from: "planning",
  valid_from: Timestamp("2025-12-27"),
  valid_until: null
}

// logs/{logId}
{
  skill_id: "planning",
  action: "create_plan",
  result: "success",
  duration_ms: 3420,
  timestamp: Timestamp,
  observation_ref: "obs_abc123"  // Masked output reference
}
```

### Qdrant Collections

```python
# Collection: skills
{
  "id": "planning",
  "vector": embed(skill_description),
  "payload": {
    "name": "planning",
    "category": "development",
    "last_updated": "2025-12-27"
  }
}

# Collection: knowledge
{
  "id": "learn_001",
  "vector": embed(learning_text),
  "payload": {
    "source_skill": "code-review",
    "type": "insight",
    "firebase_ref": "decisions/dec_xyz"  # Link to source of truth
  }
}

# Collection: errors
{
  "id": "err_001",
  "vector": embed(error_description),
  "payload": {
    "solution": "...",
    "source_skill": "debugging",
    "firebase_ref": "logs/log_abc"
  }
}
```

### Context Optimization Patterns

**1. Progressive Disclosure**
```python
# Skill discovery - load only names/descriptions
available_skills = [
  {"name": "planning", "description": "Create implementation plans"},
  {"name": "debugging", "description": "Investigate issues"},
  # ... 57 more
]

# On activation - load full content
if task_matches("planning"):
    full_skill = read_info_md("/skills/planning/info.md")
```

**2. Observation Masking**
```python
if len(tool_output) > 1000:
    ref_id = store_to_firebase(tool_output)
    masked = f"[Ref:{ref_id}] Key findings: {summarize(tool_output)}"
    return masked
```

**3. Compaction Trigger**
```python
if context_tokens / context_limit > 0.8:
    # Summarize old turns
    # Compact info.md ## Memory
    # Archive verbose outputs
    context = compact(context)
```

**4. Temporal Query**
```python
def get_preference_at_time(user_id, key, query_time):
    """What was the user's preference at a specific time?"""
    return db.collection("entities") \
        .where("type", "==", "user_preference") \
        .where("key", "==", key) \
        .where("valid_from", "<=", query_time) \
        .where("valid_until", ">", query_time) \
        .get()
```

### Resilience Patterns

**Source of Truth Hierarchy**
```
Firebase (Primary) → Qdrant (Derived) → info.md (Cache)
```

**Graceful Degradation**
```python
async def find_similar(query: str):
    try:
        return await qdrant.search("knowledge", embed(query))
    except QdrantError:
        # Fallback to Firebase keyword search
        return await firebase_keyword_search(query)
```

**Rebuild Capability**
```python
async def rebuild_qdrant_from_firebase():
    """Rebuild Qdrant if corrupted or lost."""
    decisions = db.collection("decisions").get()
    for doc in decisions:
        qdrant.upsert("knowledge", [{
            "id": doc.id,
            "vector": embed(doc["condition"] + doc["action"]),
            "payload": {"firebase_ref": f"decisions/{doc.id}"}
        }])
```

## Implementation Priority

| Phase | Component | Effort |
|-------|-----------|--------|
| 1 | Firebase temporal schema | 1h |
| 2 | Qdrant collections setup | 1h |
| 3 | Progressive disclosure in skill loading | 1h |
| 4 | Observation masking | 1h |
| 5 | Compaction triggers | 1h |
| 6 | Temporal queries | 1h |
| 7 | Rebuild/fallback patterns | 1h |

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Memory retrieval accuracy | >90% | Benchmark with test queries |
| Context compaction ratio | 50-70% | Tokens before/after |
| Temporal query accuracy | 100% | Time-travel tests |
| Qdrant fallback works | Yes | Chaos testing |

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Source of truth | Firebase | Structured, temporal, relationships |
| Semantic search | Qdrant | Derived index, rebuildable |
| Temporal validity | Full | valid_from/valid_until on all facts |
| Context optimization | All patterns | Progressive, masking, compaction |
| Per-skill memory | info.md | Fast local read, Firebase backup |

## Unresolved Questions

1. Compaction frequency - after each task or on threshold?
2. Entity relationship depth - how many hops to traverse?
3. Embedding model consistency - what if we change models?

## References

- [Agent Skills for Context Engineering](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)
- memory-systems skill
- context-optimization skill
- context-fundamentals skill
