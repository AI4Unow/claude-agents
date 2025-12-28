---
phase: 1
title: "Core Infrastructure"
status: pending
effort: 4h
priority: P1
dependencies: []
---

# Phase 1: Core Infrastructure

## Context

- Parent: [Unified II Framework](./plan.md)
- Architecture: [Final Architecture Report](../reports/brainstorm-251227-2143-final-ii-framework-architecture.md)
- Reference: [Context Engineering Skills](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)

## Overview

Build foundational components aligned with context engineering principles:
1. Skill converter with progressive disclosure
2. Firebase temporal schema
3. Context optimization patterns (masking, compaction)
4. Qdrant as derived index

## Key Insights (Context Engineering)

| Principle | Implementation |
|-----------|----------------|
| Memory Spectrum | 4 layers: Working → Short-term → Long-term → Semantic |
| Progressive Disclosure | Load skill name/description first, full on activation |
| Temporal Knowledge Graph | Firebase with valid_from/valid_until on all facts |
| Source of Truth Hierarchy | Firebase (primary) → Qdrant (derived) → info.md (cache) |
| Observation Masking | Store verbose outputs in Firebase, reference in context |
| Compaction | Summarize at 80% context usage |

## Requirements

1. Parse SKILL.md YAML frontmatter reliably
2. Implement progressive disclosure in SkillRegistry
3. Create Firebase temporal schema
4. Implement observation masking pattern
5. Add compaction trigger at 80%
6. Create Qdrant as rebuildable index

## Architecture

### Memory Spectrum Implementation

```
Layer 1: WORKING MEMORY
└── Loaded via SkillRegistry.get_full(skill_id)

Layer 2: SHORT-TERM MEMORY
└── info.md ## Memory section (Modal Volume)

Layer 3: LONG-TERM MEMORY
└── Firebase collections with temporal validity

Layer 4: SEMANTIC INDEX
└── Qdrant (derived from Firebase, rebuildable)
```

### Firebase Temporal Schema

```javascript
// skills/{skillId}
{
  name: "planning",
  description: "Create implementation plans",  // For progressive disclosure
  config: { ... },
  stats: { runCount, successRate, lastRun },
  memoryBackup: "..."  // Backup of info.md ## Memory
}

// entities/{entityId}
{
  type: "user_preference",
  key: "output_format",
  value: "markdown",
  valid_from: Timestamp,
  valid_until: null,  // null = current
  source_skill: "planning"
}

// decisions/{decisionId}
{
  condition: "user asks for code review",
  action: "activate code-review skill",
  confidence: 0.92,
  learned_from: "planning",
  valid_from: Timestamp,
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

// observations/{obsId}  (for masked outputs)
{
  content: "...",  // Full verbose output
  summary: "...",  // Key points
  created: Timestamp
}
```

### Progressive Disclosure in SkillRegistry

```python
class SkillRegistry:
    def discover(self, path: Path) -> List[SkillSummary]:
        """Return only name + description for all skills."""
        summaries = []
        for skill_dir in path.iterdir():
            summaries.append(SkillSummary(
                name=skill_dir.name,
                description=self._extract_description(skill_dir)
            ))
        return summaries

    def get_full(self, name: str) -> Skill:
        """Load full skill content on activation."""
        return self._parse_full_skill(self.path / name)
```

### Observation Masking

```python
async def mask_observation(output: str, threshold: int = 1000) -> str:
    """Store verbose output, return reference."""
    if len(output) <= threshold:
        return output

    # Store in Firebase
    ref = await db.collection("observations").add({
        "content": output,
        "summary": await summarize(output),
        "created": datetime.utcnow()
    })

    return f"[Ref:{ref.id}] Key: {await summarize(output, max_tokens=50)}"
```

### Compaction Trigger

```python
async def maybe_compact(context_tokens: int, limit: int):
    """Compact context if above 80% usage."""
    if context_tokens / limit > 0.8:
        # Summarize old conversation turns
        # Compact info.md ## Memory section
        # Replace verbose outputs with references
        return await compact_context()
```

### Qdrant as Derived Index

```python
async def rebuild_qdrant_from_firebase():
    """Rebuild Qdrant if corrupted or lost."""
    # Skills collection
    skills = await db.collection("skills").get()
    for skill in skills:
        await qdrant.upsert("skills", [{
            "id": skill.id,
            "vector": embed(skill["description"]),
            "payload": {"name": skill["name"], "firebase_ref": f"skills/{skill.id}"}
        }])

    # Knowledge collection from decisions
    decisions = await db.collection("decisions").get()
    for dec in decisions:
        await qdrant.upsert("knowledge", [{
            "id": dec.id,
            "vector": embed(f"{dec['condition']} {dec['action']}"),
            "payload": {"firebase_ref": f"decisions/{dec.id}"}
        }])

async def find_similar_with_fallback(query: str):
    """Semantic search with Firebase fallback."""
    try:
        return await qdrant.search("knowledge", embed(query))
    except QdrantError:
        # Fallback to Firebase keyword search
        return await firebase_keyword_search(query)
```

## Related Code Files

| File | Purpose |
|------|---------|
| `agents/main.py` | Modal app, sync_skills_from_github() |
| `agents/src/agents/base.py` | BaseAgent with read_skill_info() |
| `agents/src/services/firebase.py` | Firebase client |
| `agents/src/services/qdrant.py` | Qdrant client |
| `~/.claude/skills/*/SKILL.md` | Source skills (59 total) |

## Implementation Steps

### Skill Converter
- [ ] Create `agents/scripts/skill-to-modal.py` converter
- [ ] Add YAML frontmatter parser (PyYAML)
- [ ] Add markdown body extraction
- [ ] Add mutable section appending (## Memory, ## Error History)

### SkillRegistry with Progressive Disclosure
- [ ] Create `agents/src/skills/registry.py`
- [ ] Implement discover() - returns name + description only
- [ ] Implement get_full() - loads full content on activation
- [ ] Add Firebase sync for skill stats

### Firebase Temporal Schema
- [ ] Create skills collection with temporal fields
- [ ] Create entities collection with valid_from/valid_until
- [ ] Create decisions collection with temporal validity
- [ ] Create logs collection with observation_ref
- [ ] Create observations collection for masked outputs

### Context Optimization
- [ ] Implement observation masking function
- [ ] Implement compaction trigger at 80%
- [ ] Add summarization for compaction

### Qdrant as Derived Index
- [ ] Create rebuild_qdrant_from_firebase() function
- [ ] Implement fallback to Firebase keyword search
- [ ] Add health check for Qdrant availability

### Integration
- [ ] Extend sync_skills_from_github() to run converter
- [ ] Add unit tests for all components

## Todo List

- [ ] skill-to-modal.py: parse + convert
- [ ] SkillRegistry: progressive disclosure
- [ ] Firebase: temporal schema
- [ ] Observation masking
- [ ] Compaction trigger
- [ ] Qdrant: rebuild + fallback
- [ ] Integration tests

## Success Criteria

1. Converter handles all 59 SKILL.md files
2. Registry uses progressive disclosure
3. Firebase has temporal schema with valid_from/valid_until
4. Observation masking works for outputs > 1000 tokens
5. Compaction triggers at 80% context usage
6. Qdrant rebuild from Firebase works
7. Fallback to Firebase keyword search works

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| YAML parse errors | High | Validate all 59 files before deploy |
| Temporal query complexity | Medium | Start with simple queries, iterate |
| Embedding model changes | Medium | Store model version with embeddings |
| Compaction quality | Medium | Test with real conversations |

## Security Considerations

- Sanitize skill names to prevent path traversal
- Validate YAML to prevent injection
- Secure Firebase rules for observation storage

## Next Steps

→ Phase 2: Migrate priority skills with memory patterns
