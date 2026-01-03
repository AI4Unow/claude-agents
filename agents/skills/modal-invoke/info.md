---

name: modal-invoke
description: Invoke Modal-deployed II Framework skills from Claude Code.
category: general
deployment: remote
---

# Modal Invoke

Invoke Modal-deployed II Framework skills from Claude Code.

## When to Use

Use this skill when:
- Task needs cloud resources (GPU, high memory)
- Running long-duration operations
- Accessing Modal-specific integrations
- Parallel skill execution required
- Quality-critical output needing evaluation loop

## Prerequisites

- Modal deployment running at `https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run`
- Skills deployed to Modal Volume

## Execution Modes

| Mode | Use Case | Example |
|------|----------|---------|
| `simple` | Direct skill execution | Single, clear task |
| `routed` | Auto-select best skill | Unknown which skill to use |
| `orchestrated` | Complex multi-step tasks | "Build auth system with tests" |
| `chained` | Sequential pipeline | research → planning → code-review |
| `evaluated` | Quality-critical output | Customer-facing content |

## Usage Examples

### Simple Execution
```bash
curl -X POST https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run/api/skill \
  -H "Content-Type: application/json" \
  -d '{"skill": "planning", "task": "Create auth system plan", "mode": "simple"}'
```

### Routed (Auto-Select Skill)
```bash
curl -X POST .../api/skill \
  -d '{"task": "Help me debug this error", "mode": "routed"}'
```

### Orchestrated (Complex Tasks)
```bash
curl -X POST .../api/skill \
  -d '{"task": "Build a complete login system with tests and documentation", "mode": "orchestrated"}'
```

### Chained Execution
```bash
curl -X POST .../api/skill \
  -d '{"skills": ["research", "planning", "code-review"], "task": "Design a caching system", "mode": "chained"}'
```

### With Quality Evaluation
```bash
curl -X POST .../api/skill \
  -d '{"skill": "planning", "task": "Create customer onboarding flow", "mode": "evaluated"}'
```

## Available Skills

Query available skills:
```bash
curl https://duc-a-nguyen--claude-agents-telegram-chat-agent.modal.run/api/skills
```

### Development Skills
- planning
- debugging
- code-review
- research
- backend-development
- frontend-development
- mobile-development

### Design Skills
- ui-ux-pro-max
- canvas-design
- ui-styling

### Document Skills
- pdf
- docx
- pptx
- xlsx

### Media Skills
- ai-multimodal
- media-processing
- ai-artist
- image-enhancer
- video-downloader

## Response Format

```json
{
  "ok": true,
  "result": "...",
  "skill": "planning",
  "mode": "simple",
  "duration_ms": 3420
}
```

## Error Handling

```json
{
  "ok": false,
  "error": "Skill not found: xyz"
}
```

## Context Passing

Pass project context:
```json
{
  "skill": "planning",
  "task": "Add user authentication",
  "context": {
    "project": "my-saas-app",
    "stack": "Next.js, PostgreSQL",
    "constraints": ["no external auth providers"]
  }
}
```

## Memory

<!-- Per-skill memory: patterns, preferences, learnings -->

## Error History

<!-- Past errors and fixes -->
