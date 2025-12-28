---
name: gemini-thinking
description: Configurable reasoning depth for complex analysis. Adjust thinking level from minimal (fast) to high (thorough).
category: reasoning
deployment: remote
triggers:
  - "think deeply about"
  - "analyze step by step"
  - "reason through"
  - "solve this problem"
---

# Gemini Thinking

Adjustable reasoning depth for different complexity levels.

## Thinking Levels

| Level | Use Case | Speed |
|-------|----------|-------|
| minimal | Simple facts | <2s |
| low | Basic reasoning | 2-5s |
| medium | General analysis | 5-15s |
| high | Complex problems | 15-60s |

## Usage

```
/skill gemini-thinking "Analyze the trade-offs of microservices vs monolith"
```

With explicit level:
```json
{
  "skill": "gemini-thinking",
  "task": "Prove the Pythagorean theorem",
  "context": {"thinking_level": "high"}
}
```

## Best For

- Mathematical proofs
- Code debugging
- Architecture decisions
- Complex problem solving
- Multi-step reasoning
