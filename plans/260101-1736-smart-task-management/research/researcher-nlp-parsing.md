# Hybrid NLP Task Parsing Research Report

## 1. Library: `dateparser`
Deterministic library for temporal expression normalization.

### Capabilities
- **Relative Parsing**: "in 2 hours", "next Friday at 3pm".
- **Multilingual**: 200+ locales, auto-detection.
- **Settings**: `RELATIVE_BASE` (anchor to message time), `DATE_ORDER` (DMY/MDY resolution).

### Limitations
- **False Positives**: Can "hallucinate" dates from random numbers. Use `STRICT_PARSING`.
- **Performance**: Slower than regex due to locale checks.
- **Ambiguity**: Needs hints for `01/02/03`.

## 2. Library: `spaCy` NER
Linguistic engine for structural extraction.

### Strengths
- **Entity Linking**: Connects "call John" (Action) to "Tuesday" (Time).
- **Custom Components**: Integrate `date-spacy` to bridge spaCy + dateparser.
- **Speed**: Optimized for high-throughput stream processing.

## 3. LLM Function Calling (Claude/Gemini)
Primary layer for intent discovery and candidate extraction.

### Strategy
- **Intent**: Classify as `TASK` vs `REMINDER` vs `QUERY`.
- **Candidate Extraction**: Extract raw strings: `{"task": "Buy milk", "time_str": "after work tomorrow"}`.
- **System Prompt**: MUST include `Current Time: 2026-01-01 18:20` for relative resolution.

## 4. Hybrid Best Practices (Layered Architecture)
1. **Layer 1 (LLM)**: Extract raw `intent`, `action`, and `time_candidate`.
2. **Layer 2 (spaCy)**: Validate `action` entities (Person, Org, Loc).
3. **Layer 3 (dateparser)**: Normalize `time_candidate` using `RELATIVE_BASE`.

### Code Example (Hybrid Concept)
```python
# LLM Result: {"task": "Email Sarah about the report", "time_raw": "on Monday morning"}
import dateparser
from datetime import datetime

base_time = datetime(2026, 1, 1, 18, 20) # Extracted from msg metadata
parsed_dt = dateparser.parse(
    "on Monday morning",
    settings={'RELATIVE_BASE': base_time, 'PREFER_DATES_FROM': 'future'}
)
# Result: 2026-01-05 09:00:00
```

## Recommended Tech Stack
- **Parsing**: `dateparser`
- **NER**: `spaCy` (model `en_core_web_md`)
- **Orchestration**: LLM Tool/Function calling (Gemini 2.0 Flash)

## Unresolved Questions
- How to handle recurring tasks (e.g., "every Monday") deterministically without complex RRule logic?
- Latency overhead of LLM + spaCy pipeline for real-time Telegram response?
