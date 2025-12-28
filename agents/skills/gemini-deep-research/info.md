---
name: gemini-deep-research
description: Multi-step agentic research with web grounding, citations, and professional reports. Use for complex topics requiring comprehensive analysis.
category: research
deployment: remote
triggers:
  - "research"
  - "deep dive"
  - "analyze market"
  - "investigate"
  - "comprehensive report on"
---

# Gemini Deep Research

Autonomous research agent powered by Gemini with Google Search grounding.

## Capabilities

- **Task Decomposition:** Breaks complex queries into searchable sub-queries
- **Web Grounding:** Uses Google Search for real-time, factual data
- **Iterative Refinement:** Identifies gaps and generates follow-up queries
- **Citation Extraction:** Provides sources for all claims
- **Report Synthesis:** Creates professional markdown reports

## Usage

```
/skill gemini-deep-research "Research AI agent frameworks in 2025"
```

## Parameters

| Param | Default | Description |
|-------|---------|-------------|
| max_iterations | 10 | Max sub-queries to research |
| model | gemini-2.0-flash-001 | Gemini model |

## Output

Returns structured research report with:
- Executive summary
- Key findings with analysis
- Recommendations
- Citations with URLs

## Async Behavior

Long-running researches (>30s) stream progress updates to Telegram.
