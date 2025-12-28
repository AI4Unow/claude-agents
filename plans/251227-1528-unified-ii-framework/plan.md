---
title: "Unified II Framework Architecture"
description: "Share 59 Claude Code skills between local and Modal.com with hybrid memory"
status: completed
priority: P1
effort: 16h
branch: main
tags: [modal, skills, ii-framework, architecture, memory, context-engineering, claude-agents-sdk]
created: 2025-12-27
updated: 2025-12-27
completed: 2025-12-27
---

# Unified II Framework Architecture

## Overview

Build unified "Information + Implementation" architecture sharing 59 Claude Code skills between local and Modal.com environments, aligned with:
- **Context Engineering** best practices (memory spectrum, progressive disclosure)
- **Claude Agents SDK** philosophy (routing, orchestrator-workers, evaluator-optimizer)

## Key Components

### Core Infrastructure
1. **skill-to-modal.py** - Convert SKILL.md (immutable) to info.md (mutable)
2. **SkillRegistry** - Unified discovery with progressive disclosure
3. **Memory Spectrum** - 4-layer architecture (Working → Short-term → Long-term → Semantic)
4. **Temporal Knowledge Graph** - Firebase with valid_from/valid_until on all facts
5. **Context Optimization** - Compaction, masking, progressive disclosure
6. **Git-Sync** - Hot-reload scripts without redeploying

### Agent Patterns (Claude Agents SDK)
7. **SkillRouter** - Semantic routing to select skills (Qdrant-based)
8. **Orchestrator** - Decompose tasks, delegate to skill workers, synthesize
9. **ChainedExecution** - Sequential skill execution with output→input
10. **EvaluatorOptimizer** - Generate→Evaluate→Improve quality loop

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 II FRAMEWORK + CLAUDE AGENTS SDK                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT → [1. ROUTING] → [2. ORCHESTRATOR] → [3. WORKERS] → [4. EVALUATOR]   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  1. ROUTING LAYER (SkillRouter)                                        │  │
│  │     User Request → Qdrant semantic search → Best matching skills       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  2. ORCHESTRATOR                                                       │  │
│  │     • Decompose complex tasks into subtasks                            │  │
│  │     • Delegate to skill workers (parallel or chained)                  │  │
│  │     • Synthesize worker outputs into final response                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│           │                    │                    │                        │
│           ▼                    ▼                    ▼                        │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                 │
│  │ Skill Worker │     │ Skill Worker │     │ Skill Worker │  PARALLEL       │
│  │ (info.md)    │     │ (info.md)    │     │ (info.md)    │                 │
│  │ + tools      │     │ + tools      │     │ + tools      │                 │
│  └──────────────┘     └──────────────┘     └──────────────┘                 │
│           │                    │                    │                        │
│           └────────────────────┼────────────────────┘                        │
│                                ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  3. PROMPT CHAINING (if sequential dependencies)                       │  │
│  │     Skill₁ output → Skill₂ input → Skill₃ input → Final               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                │                                             │
│                                ▼                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  4. EVALUATOR-OPTIMIZER (quality-critical outputs)                     │  │
│  │     Output → LLM-as-Judge → Score < 0.8? → Feedback → Regenerate      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                │                                             │
│                                ▼                                             │
│  OUTPUT + Memory Update (Firebase → Qdrant → info.md)                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Memory Architecture (Context Engineering Aligned)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MEMORY SPECTRUM                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 1: WORKING MEMORY (Context Window)                                    │
│  └── Current skill content, active task, recent outputs                      │
│                                                                              │
│  Layer 2: SHORT-TERM MEMORY (Modal Volume - info.md)                         │
│  └── Per-skill memory, session patterns, compacted summaries                 │
│                                                                              │
│  Layer 3: LONG-TERM MEMORY (Firebase - Primary Source of Truth)              │
│  ├── skills/{id} - config, stats, memory backup                              │
│  ├── entities/{id} - with valid_from/valid_until (TEMPORAL)                  │
│  ├── decisions/{id} - learned rules with temporal validity                   │
│  └── logs/{id} - execution history, masked observation refs                  │
│                                                                              │
│  Layer 4: SEMANTIC INDEX (Qdrant - Derived, Rebuildable)                     │
│  ├── skills - semantic skill matching (for ROUTING)                          │
│  ├── knowledge - cross-skill insights (linked to Firebase)                   │
│  ├── errors - error pattern matching                                         │
│  └── conversations - chat history                                            │
│                                                                              │
│  HIERARCHY: Firebase (Primary) → Qdrant (Derived) → info.md (Cache)          │
│  FALLBACK: If Qdrant fails → Firebase keyword search                         │
│  REBUILD: firebase → embed → qdrant                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Context Optimization Patterns

| Pattern | Trigger | Action |
|---------|---------|--------|
| Progressive Disclosure | Skill discovery | Load name/description first, full on activation |
| Observation Masking | Output > 1000 tokens | Store in Firebase, reference in context |
| Compaction | Context > 80% | Summarize old turns, compact ## Memory |
| Temporal Query | Any fact lookup | Filter by valid_from/valid_until |

## Execution Modes

| Mode | Pattern | When to Use |
|------|---------|-------------|
| Simple | Direct skill execution | Single, clear task |
| Routed | Routing → Skill | Unknown best skill |
| Orchestrated | Orchestrator → Workers | Complex, decomposable |
| Chained | Skill₁ → Skill₂ → ... | Sequential dependencies |
| Evaluated | Generate → Evaluate → Loop | Quality-critical output |

## Phases

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| 1 | [Core Infrastructure](./phase-01-core-infrastructure.md) | 5h | **completed** |
| 2 | [Priority Skills Migration](./phase-02-priority-skills-migration.md) | 3h | **completed** |
| 3 | [Document Skills](./phase-03-document-skills.md) | 2h | **completed** |
| 4 | [Media & Procaffe Scripts](./phase-04-media-procaffe-scripts.md) | 2h | **completed** |
| 5 | [Claude Code Integration](./phase-05-claude-code-integration.md) | 4h | **completed** |

## Implementation Summary (2025-12-27)

### Files Created

**Core Infrastructure (Phase 1):**
- `agents/scripts/skill-to-modal.py` - SKILL.md → info.md converter
- `agents/src/skills/registry.py` - SkillRegistry with progressive disclosure
- `agents/src/core/router.py` - Semantic skill routing
- `agents/src/core/orchestrator.py` - Multi-skill task orchestration
- `agents/src/core/chain.py` - Sequential skill pipelines
- `agents/src/core/evaluator.py` - Quality evaluation loops
- `agents/src/core/context_optimization.py` - Masking & compaction

**Firebase Temporal Schema (Phase 1):**
- Updated `agents/src/services/firebase.py` with:
  - `create_entity()` / `get_entity()` with valid_from/valid_until
  - `create_decision()` / `get_decisions()` for learned rules
  - `store_observation()` / `get_observation()` for masked outputs
  - `keyword_search()` fallback

**Qdrant Extensions (Phase 1):**
- Updated `agents/src/services/qdrant.py` with:
  - `store_skill()` / `search_skills()` for routing
  - `rebuild_from_firebase()` disaster recovery
  - `search_with_fallback()` graceful degradation
  - `health_check()` monitoring

**Skills Converted (Phases 2-4):**
- 23 skills converted to Modal format in `agents/skills/`
- Priority: planning, debugging, code-review, research, backend/frontend/mobile-development
- Design: ui-ux-pro-max, canvas-design, ui-styling
- Documents: pdf, docx, pptx, xlsx
- Media: ai-multimodal, media-processing, ai-artist, image-enhancer, video-downloader

**Claude Code Integration (Phase 5):**
- Added `/api/skill` endpoint to `agents/main.py`
- Added `/api/skills` listing endpoint
- Execution modes: simple, routed, orchestrated, chained, evaluated
- Created `~/.claude/skills/modal-invoke/SKILL.md` for Claude Code

### Dependencies Added
- PyYAML, python-docx, docxtpl, docx2python
- openpyxl, formulas, python-pptx
- pypdf, pdfplumber

## Success Criteria

1. 59/59 Claude Code skills accessible on Modal
2. Skill routing accuracy > 90%
3. Orchestrator correctly decomposes 85%+ of complex tasks
4. Evaluator improves output quality by 20%+
5. Memory retrieval accuracy > 90%
6. Temporal queries work (time-travel)
7. Context compaction achieves 50-70% reduction
8. <60s sync latency from Git push to Modal update

## Validation Summary

**Validated:** 2025-12-27
**Questions asked:** 10
**Context Engineering Aligned:** Yes
**Claude Agents SDK Aligned:** Yes

### Confirmed Decisions

**Architecture:**
- Source of truth: **Firebase** (structured, temporal, relationships)
- Semantic search: **Qdrant** (derived index, rebuildable from Firebase)
- Per-skill memory: **info.md** (fast local read, Firebase backup)
- Temporal validity: **Full** (valid_from/valid_until on all facts)

**Agent Patterns (Claude Agents SDK):**
- Routing: **Qdrant semantic search** on skill descriptions
- Orchestration: **Decompose → Delegate → Synthesize**
- Chaining: **Output→Input** passing between sequential skills
- Evaluation: **LLM-as-Judge** with feedback loop (max 3 iterations)

**Context Optimization:**
- Progressive disclosure: **Yes** (load skill description first)
- Observation masking: **Yes** (store verbose, reference in context)
- Compaction: **Yes** (at 80% context usage)

**Integration:**
- Modal integration: **HTTP webhook** (/api/skill endpoint)
- Memory sync: **After each task** (Firebase primary, async to Qdrant)
- Procaffe scripts: **All** (API→Modal, browser→local)

**Document Processing:**
- XLSX: **Python-only** (formulas library, no LibreOffice)
- PDF conversion: **Cloud API** (CloudConvert/Gotenberg)

### Action Items

**Phase 1: Core Infrastructure**
- [ ] Implement Firebase temporal schema (valid_from/valid_until)
- [ ] Add progressive disclosure to skill loading
- [ ] Implement observation masking
- [ ] Add compaction triggers at 80%
- [ ] Implement SkillRouter with Qdrant semantic search
- [ ] Implement Orchestrator class
- [ ] Implement ChainedExecution class
- [ ] Implement EvaluatorOptimizer class

**Phase 2-5:**
- [ ] Create Qdrant rebuild-from-Firebase function
- [ ] Use Python libs + Cloud API for docs
- [ ] Include all Procaffe scripts
- [ ] Create /api/skill HTTP endpoint

## Related Docs

- [Claude Agents SDK Integration](../reports/brainstorm-251227-2150-claude-agents-sdk-integration.md)
- [Final Architecture Brainstorm](../reports/brainstorm-251227-2143-final-ii-framework-architecture.md)
- [LibreOffice Alternatives](../reports/brainstorm-251227-1645-libreoffice-alternatives.md)
- [Initial Brainstorm](../reports/brainstorm-251227-1528-unified-ii-architecture.md)
- [System Architecture](../../docs/system-architecture.md)
- [Skills Deployment Audit](../251227-1355-skills-deployment-audit/plan.md)
- [Context Engineering Skills](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)
- [Building Effective Agents](https://anthropic.com/research/building-effective-agents)
