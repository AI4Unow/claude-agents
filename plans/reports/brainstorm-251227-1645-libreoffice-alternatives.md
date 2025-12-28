# Brainstorm: LibreOffice Alternatives for Document Processing

## Problem Statement

Evaluate whether LibreOffice is the best open-source option for document processing in Modal.com deployment, specifically for:
- DOCX read/write/template operations
- XLSX formula recalculation
- PDF conversion (DOCX→PDF, XLSX→PDF)

## Key Constraints

- Modal.com serverless environment
- Container size impacts cold start time
- Cost efficiency for high-volume processing
- Must handle DOCX→PDF conversion reliably

## Evaluated Approaches

### Option 1: LibreOffice (Full Suite)

| Pros | Cons |
|------|------|
| 100% MS Office compatibility | 500MB+ container size |
| Battle-tested | 5-10s cold start |
| Handles all edge cases | Memory heavy (200MB+) |

**Verdict:** ❌ Too heavy for serverless

### Option 2: Python-Only Libraries

| Library | Purpose | Size |
|---------|---------|------|
| python-docx | DOCX read/write | ~5MB |
| docxtpl | DOCX templates (Jinja2) | ~5MB |
| docx2python | Content extraction | ~2MB |
| formulas/PyCel | XLSX formula calc | ~2MB |
| openpyxl | XLSX read/write | ~5MB |

| Pros | Cons |
|------|------|
| Tiny footprint (~20MB total) | No PDF conversion |
| Fast cold start (<1s) | ~90% formula coverage |
| Pure Python, no deps | Complex layouts may fail |

**Verdict:** ✅ Best for read/write operations

### Option 3: Cloud API for PDF Conversion

| Service | Free Tier | Paid |
|---------|-----------|------|
| CloudConvert | 25/day | $8/1000 |
| Gotenberg | Self-hosted | Free |
| ILovePDF | 1000/month | $4/mo |

| Pros | Cons |
|------|------|
| No container bloat | External dependency |
| High fidelity PDF output | Network latency |
| Gotenberg = self-hosted | API costs (if not Gotenberg) |

**Verdict:** ✅ Best for PDF conversion

### Option 4: unoserver (Modern LibreOffice Wrapper)

Persistent LibreOffice daemon that avoids cold-start penalty per conversion.

| Pros | Cons |
|------|------|
| Faster than raw LibreOffice | Still needs LibreOffice installed |
| Production-ready | 500MB+ container |
| Modern replacement for unoconv | - |

**Verdict:** ⚠️ Only if Gotenberg/Cloud API unavailable

## Final Recommendation

### Tiered Architecture

```
Tier 1: Standard Modal Image (~50MB)
├── python-docx + docxtpl   → DOCX read/write/template
├── openpyxl + formulas     → XLSX read/write/formulas
├── python-pptx             → PPTX read/write
└── pypdf + pdfplumber      → PDF read/extract

Tier 2: PDF Conversion Service (Separate)
└── CloudConvert API or Gotenberg (self-hosted)
    → DOCX/XLSX/PPTX → PDF conversion
```

### Rationale

1. **80/20 Rule**: 80% of document tasks are read/write/template - handled by lightweight Python libs
2. **Isolate Heavy Ops**: PDF conversion is infrequent, isolate to external service
3. **Cost Efficient**: Gotenberg is free (self-hosted), CloudConvert has generous free tier
4. **Fast Cold Start**: Standard image stays under 100MB, <1s cold start

## Implementation Considerations

1. **Formula Coverage**: Test with real spreadsheets to verify `formulas` library handles your use cases
2. **PDF Fidelity**: Test complex DOCX layouts with CloudConvert before committing
3. **Fallback Strategy**: If formula/layout fails, queue for manual review or Gotenberg fallback

## Success Metrics

| Metric | Target |
|--------|--------|
| Standard image size | <100MB |
| Cold start time | <1s |
| Formula coverage | >90% |
| PDF conversion success | >99% |

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LibreOffice in main container | ❌ No | Too heavy (500MB+) |
| XLSX formula handling | `formulas` lib | Pure Python, 90% coverage |
| PDF conversion | Cloud API | Isolate heavy deps |
| DOCX processing | Tiered | Read/write lightweight, PDF separate |

## Unresolved Questions

1. Which specific Cloud API to use? (CloudConvert vs Gotenberg vs ILovePDF)
2. Fallback strategy if formula library fails on complex spreadsheet?
3. Rate limiting for PDF conversion API?

## Next Steps

- [x] Update Phase 3 of II Framework plan with tiered approach
- [ ] Test `formulas` library with real spreadsheets from Procaffe
- [ ] Evaluate Gotenberg vs CloudConvert for PDF conversion
- [ ] Implement PDF conversion service
