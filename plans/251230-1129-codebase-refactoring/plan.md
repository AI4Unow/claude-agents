---
title: "Codebase Refactoring - Modal.com Self-Improving Agents"
description: "5-phase refactoring to address critical technical debt in main.py (3106 lines) and firebase.py (1413 lines)"
status: completed
priority: P1
effort: 80h
branch: main
tags: [refactoring, technical-debt, security, architecture]
created: 2025-12-30
completed: 2025-12-30
---

# Codebase Refactoring Plan

**Objective:** Reduce technical debt from ~35% to <15% by splitting monolithic files, fixing security gaps, and improving maintainability.

## Summary Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| main.py lines | 3106 | ~500 | <500 ✓ |
| firebase.py lines | 1413 | 12 modules (~1562) | Split ✓ |
| Critical issues | 5 | 0 | 0 ✓ |
| Test coverage | ~60% | +4 test files | 80%+ |

## Phase Overview

| Phase | Focus | Effort | Status | Progress |
|-------|-------|--------|--------|----------|
| [Phase 1](./phase-01-security-fixes.md) | Security fixes | 8h | completed | 100% |
| [Phase 2](./phase-02-extract-routes.md) | Extract FastAPI routes | 16h | completed | 100% |
| [Phase 3](./phase-03-extract-commands.md) | Command router pattern | 16h | completed | 100% |
| [Phase 4](./phase-04-refactor-services.md) | Split services, circuit decorator | 24h | completed | 100% |
| [Phase 5](./phase-05-testing-docs.md) | Testing and documentation | 16h | completed | 100% |

## Critical Issues Addressed

1. **Monolithic main.py** (3106 lines) - Split into api/, commands/, handlers/, execution/
2. **God service firebase.py** (1413 lines) - Split into domain services
3. **Missing GitHub webhook verification** - Add HMAC-SHA256 validation
4. **No input validation** - Add InputValidator class
5. **Firebase race condition** - Add threading lock to global state

## Dependencies

- Phase 2 depends on Phase 1 (security fixes first)
- Phase 3 depends on Phase 2 (routes extracted before commands)
- Phase 4 can run parallel to Phase 3
- Phase 5 depends on all previous phases

## Related Reports

- [Comprehensive Analysis](../reports/codebase-review-251230-1119-comprehensive-analysis.md)
- [main.py Review](../reports/code-reviewer-251230-1121-main-py-review.md)
- [firebase.py Review](../reports/code-reviewer-251230-1121-firebase-service-review.md)
- [state.py Review](../reports/code-reviewer-251230-1121-state-py-quality-review.md)

## Risk Mitigation

- Feature freeze during Phase 4 recommended
- Deploy per-phase with rollback plan
- Run existing tests after each phase

## Success Criteria

- All 5 critical issues resolved
- main.py reduced to <500 lines
- firebase.py split into 6+ domain services
- 80%+ test coverage on new modules
- No regression in production behavior
