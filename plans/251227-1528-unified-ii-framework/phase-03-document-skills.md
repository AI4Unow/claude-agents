---
phase: 3
title: "Document Skills"
status: pending
effort: 2h
priority: P2
dependencies: [phase-02]
---

# Phase 3: Document Skills

## Context

- Parent: [Unified II Framework](./plan.md)
- Depends on: [Phase 2 - Priority Skills Migration](./phase-02-priority-skills-migration.md)

## Overview

Migrate document processing skills using tiered approach: Python libraries for read/write, Cloud API/Gotenberg for PDF conversion.

## Document Skills (4 skills)

| Skill | Purpose | Dependencies |
|-------|---------|--------------|
| pdf | PDF reading/extraction | pypdf, pdfplumber |
| docx | Word document processing | python-docx, docxtpl, docx2python |
| pptx | PowerPoint processing | python-pptx |
| xlsx | Excel with formulas | openpyxl, formulas (PyCel) |

## Key Insights (Updated after Brainstorm)

- **NO LibreOffice in main container** - too heavy (500MB+)
- XLSX formula recalc: Use `formulas` or `PyCel` Python library (~90% coverage)
- DOCX→PDF: Use **Gotenberg** (self-hosted) or **CloudConvert** API
- Read/write operations: Pure Python libraries only

## Requirements

1. Convert 4 document SKILL.md → info.md
2. Use Python-only libs for read/write/template operations
3. Add Gotenberg as separate service for PDF conversion
4. Test formula recalculation with `formulas` library

## Architecture

### Tiered Document Processing

```
┌─────────────────────────────────────────────────────────┐
│               Document Processing Tiers                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tier 1: Standard Image (~50MB)                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ • python-docx    → Read/write DOCX              │   │
│  │ • docxtpl        → Template + Jinja2 injection  │   │
│  │ • docx2python    → Deep content extraction      │   │
│  │ • openpyxl       → XLSX read/write              │   │
│  │ • formulas       → XLSX formula calculation     │   │
│  │ • python-pptx    → PPTX read/write              │   │
│  │ • pypdf          → PDF read/extract             │   │
│  │ • pdfplumber     → PDF table extraction         │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Tier 2: PDF Conversion (Separate Service)              │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Option A: Gotenberg (Self-hosted, ~200MB)       │   │
│  │ • Docker: gotenberg/gotenberg:8                 │   │
│  │ • REST API, pre-configured LibreOffice          │   │
│  │                                                 │   │
│  │ Option B: CloudConvert API                      │   │
│  │ • 25 free conversions/day                       │   │
│  │ • $8/1000 conversions                           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Modal Implementation

```python
# Standard image (all document read/write/template)
standard_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "python-docx",     # DOCX read/write
        "docxtpl",         # DOCX templates
        "docx2python",     # DOCX extraction
        "openpyxl",        # XLSX read/write
        "formulas",        # XLSX formula calc (NO LibreOffice!)
        "python-pptx",     # PPTX
        "pypdf",           # PDF
        "pdfplumber",      # PDF tables
    )
)

# Option A: Gotenberg for PDF conversion (self-hosted)
gotenberg_image = modal.Image.from_registry("gotenberg/gotenberg:8")

@app.function(image=gotenberg_image, container_idle_timeout=300)
def pdf_converter_service():
    """Gotenberg service for DOCX/XLSX/PPTX → PDF."""
    pass  # Gotenberg runs its own server

# Option B: CloudConvert API
@app.function(image=standard_image)
async def convert_to_pdf_cloud(file_bytes: bytes, format: str) -> bytes:
    """Use CloudConvert API for PDF conversion."""
    import cloudconvert
    # API call to CloudConvert
```

## Related Code Files

| File | Purpose |
|------|---------|
| `~/.claude/skills/document-skills/pdf/SKILL.md` | PDF source |
| `~/.claude/skills/document-skills/docx/SKILL.md` | DOCX source |
| `~/.claude/skills/document-skills/pptx/SKILL.md` | PPTX source |
| `~/.claude/skills/document-skills/xlsx/SKILL.md` | XLSX source |
| `agents/main.py` | Modal image definition |

## Implementation Steps

- [ ] Update standard_image with Python doc libraries
- [ ] Convert pdf skill (pypdf + pdfplumber)
- [ ] Convert docx skill (python-docx + docxtpl + docx2python)
- [ ] Convert pptx skill (python-pptx)
- [ ] Convert xlsx skill (openpyxl + formulas)
- [ ] Add Gotenberg or CloudConvert integration
- [ ] Create pdf_converter Modal function
- [ ] Test DOCX read/write/template
- [ ] Test XLSX formula recalc with `formulas`
- [ ] Test PDF conversion via Gotenberg/CloudConvert

## Todo List

- [ ] Add Python doc libraries to standard image
- [ ] Convert 4 document skills
- [ ] Choose Gotenberg vs CloudConvert
- [ ] Implement PDF conversion service
- [ ] Test each document operation
- [ ] Benchmark formula coverage

## Success Criteria

1. All 4 document skills deployed on standard image
2. DOCX read/write/template works without LibreOffice
3. XLSX formulas recalculate with `formulas` library
4. PDF conversion works via Gotenberg or CloudConvert
5. **Standard image stays under 100MB**

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Formula coverage gaps | Medium | Test with real spreadsheets, fallback to API |
| Gotenberg cold start | Low | container_idle_timeout=300 |
| CloudConvert costs | Low | 25 free/day, monitor usage |
| Complex DOCX layouts | Medium | Test edge cases, document limitations |

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LibreOffice | ❌ Removed | 500MB too heavy for Modal |
| XLSX formulas | `formulas` lib | Pure Python, ~90% coverage |
| PDF conversion | Cloud API/Gotenberg | Isolate heavy deps |
| DOCX processing | Tiered approach | Read/write lightweight, PDF separate |

## Next Steps

→ Phase 4: Media & Procaffe scripts
