---
name: gemini-grounding
description: Real-time factual queries with Google Search/Maps grounding. Returns cited answers for current events, prices, locations.
category: research
deployment: both
triggers:
  - "what's the current"
  - "latest news on"
  - "find nearby"
  - "price of"
  - "today's"
---

# Gemini Grounding

Quick factual answers with real-time web data and citations.

## Features

- Google Search grounding for facts
- Google Maps grounding for locations
- Dynamic retrieval (only searches when needed)
- Inline citations with URLs

## Usage

```
/skill gemini-grounding "What's the current price of Bitcoin?"
```

## Response Time

Typically 2-5 seconds for factual queries.

## Examples

- "What's the current price of NVDA stock?"
- "Latest news on AI regulations"
- "Find cafes near Times Square"
- "Today's weather in Tokyo"
