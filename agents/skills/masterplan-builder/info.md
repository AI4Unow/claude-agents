---

name: masterplan-builder
description: Build a complete masterplan presentation (map, overview, chatbot) from a government decision documen
category: design
deployment: local
---

# Masterplan Builder Skill

Build a complete masterplan presentation (map, overview, chatbot) from a government decision document.

## When to Use
- Received a new government decision (QĐ-XXX) that needs visualization
- Want to create map + overview + chatbot for a new domain
- Following the minerals (QH-866), electricity (QH-768), and seaports (QD-1579) patterns

## Quick Start

```
/skill masterplan-builder
```

Then follow the interactive prompts.

---

## CRITICAL: Pre-Implementation Checklist

> **LESSON LEARNED (Seaport QD-1579):** 20+ bugs fixed from missing these checks. Always complete before starting.

### Before Phase 1: Read Reference Implementations

- [ ] Read `src/app/minerals/page.tsx` completely
- [ ] Read `src/components/map/province-map.tsx` for map patterns
- [ ] Read `src/components/map/province-popup.tsx` for popup patterns
- [ ] Read `src/components/filters/filter-panel.tsx` for filter patterns
- [ ] Identify ALL patterns to replicate

### Before Phase 2: Data Validation Gates

- [ ] **100% of map entities have lat/lng coordinates**
- [ ] **100% of parent entities have children** (e.g., all ports have terminals)
- [ ] Province IDs normalized to 34-group format
- [ ] Coordinates within Vietnam bounds (8-24°N, 102-115°E)

### Before Phase 3: Firebase Upload

- [ ] Upload script expected counts match JSON file counts
- [ ] Re-run upload after any JSON data updates
- [ ] Verify Firestore counts match expected after upload

### Before Phase 4: Architecture Requirements

- [ ] Page MUST use `MasterplanMapShell` wrapper
- [ ] NO standalone page layouts

### Before Phase 5: UI Consistency

- [ ] Reference minerals implementation for all components
- [ ] Copy class names exactly, only change domain content
- [ ] Use NONE_SELECTED_MARKER pattern for filter "deselect all"
- [ ] Popup shows ALL child entities (no collapse/expand)
- [ ] Marker colors distinct from Vietnam map border (avoid blue-600)
- [ ] **Import formatNumber from `@/lib/utils/format-number` for ALL number displays**
- [ ] **Use Vietnamese locale (vi-VN): dot=thousands, comma=decimals**
- [ ] **Use OverviewShell + OverviewHeader for overview page**
- [ ] **Use client-side hook with React Query for overview data fetching**

---

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: EXTRACTION                                        │
│  Read decision document → Extract structured data           │
│  Output: data/{decision}-extracted.json                     │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: DATA MODELING                                     │
│  Define types, validate JSON structure                      │
│  Output: Validated JSON ready for Firebase                  │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: FIREBASE UPLOAD                                   │
│  Create collections, upload documents                       │
│  Output: Firestore collections populated                    │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: SCAFFOLDING                                       │
│  Generate UI components, pages, tools from templates        │
│  Output: 15+ source files in src/                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 5: CUSTOMIZATION                                     │
│  Review generated files, add domain-specific logic          │
│  Output: Production-ready masterplan                        │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 6: TESTING                                           │
│  Verify map, overview, chatbot work correctly               │
│  Output: Working masterplan at /[masterplan]                │
└─────────────────────────────────────────────────────────────┘
```

## Interactive Session

### Step 1: Gather Info

I'll ask you for:
- **Decision ID**: e.g., `QD-999`
- **Masterplan name**: e.g., `forestry` (used for routes, files)
- **Vietnamese name**: e.g., `Lâm nghiệp`
- **Entity types**: e.g., `forests, reserves, processing_plants`
- **Accent color**: e.g., `emerald`, `amber`, `blue`

### Step 2: Extract Data

Provide the decision document path:
```
decisions/forestry/QD-999.docx
```

I'll read the document and extract:
- Entity lists (projects, sites, targets)
- Overview info (objectives, principles)
- Geographic data (provinces, coordinates)

You validate the extraction before proceeding.

### Step 3: Upload to Firebase

Collections created:
- `{entity}_{decision_number}` for each entity type
- `{masterplan}_search_index_{number}`
- `{masterplan}_aggregates_{number}`
- `{masterplan}_overview_{number}`

### Step 4: Scaffold Files

Generated files:

**Types & Infrastructure:**
- `src/types/{mp}.ts`
- `src/lib/firebase/{mp}.ts`
- `src/lib/firebase/constants.ts` (updated)
- `src/lib/masterplan/registry.ts` (updated)
- `src/lib/masterplan/filters/{mp}-filter-schema.ts`
- `src/hooks/use-{mp}-data.ts`

**Map Page:**
- `src/app/{mp}/page.tsx`
- `src/components/{mp}/{mp}-stats-overlay.tsx`
- `src/components/{mp}/{mp}-filter-panel.tsx`
- `src/components/{mp}/{mp}-popup.tsx`

**Overview Page:**
- `src/app/{mp}/overview/page.tsx`
- `src/components/{mp}/{mp}-stats-cards.tsx`
- `src/components/{mp}/{mp}-charts.tsx`
- `src/app/api/{mp}/overview/route.ts`

**Chatbot (AI Tools):**
- `src/lib/ai/{mp}-tools.ts`
- `src/lib/ai/toolset-registry.ts` (updated)

### Step 5: Customize

Key files to review:
1. `{mp}-tools.ts` - Add domain-specific queries
2. `{mp}-charts.tsx` - Adjust visualizations
3. `{mp}-filter-schema.ts` - Tune filter options

### Step 6: Test

```bash
npm run dev
```

Verify:
- Map: `http://localhost:3000/{masterplan}`
- Overview: `http://localhost:3000/{masterplan}/overview`
- Chatbot: Ask domain-specific questions

## Chatbot Framework

The chatbot uses a sophisticated tool-based architecture with context optimization:

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `province-tools.ts` | `src/lib/ai/` | Province resolution (shared) |
| `toolset-registry.ts` | `src/lib/ai/` | Maps masterplanId → tools + intent subsets |
| `router.ts` | `src/lib/ai/` | Query classification and intent detection |
| `utils.ts` | `src/lib/ai/` | Shared utilities |
| `{mp}-tools.ts` | `src/lib/ai/` | Domain-specific tools |

### Context Optimization (Reduces LLM tokens)

The chatbot uses 3 strategies to minimize context:

1. **Summary Gating** (~300 tokens saved)
   - Skips summary context when tool will fetch data
   - Uses `needsSummaryContext()` from router.ts

2. **History Pruning** (~200-1000 tokens saved)
   - Keeps first message (intent anchor) + last 4 messages
   - Uses `pruneConversationHistory()` in route.ts

3. **Intent-Based Tool Selection** (~500-700 tokens saved)
   - Sends 2-3 relevant tools instead of 10+
   - Uses `getToolsetByIntent()` from toolset-registry.ts

### Model Configuration

| Query Type | Primary | Fallback | Final |
|------------|---------|----------|-------|
| Simple (greetings) | Groq Llama 3.3 | Cerebras Llama 3.3 | SambaNova Llama 3.3 |
| Complex (data) | Gemini 3 Flash Preview | Cohere Command-A | - |

### Key Features

1. **Province Resolution** - Uses `resolveProvince` tool with fuzzy matching
2. **Aggregates Fast Path** - Stats queries use pre-computed aggregates (~50ms vs ~1500ms)
3. **Region Support** - Queries support "miền Bắc", "miền Trung", "miền Nam"
4. **Error Wrapping** - All tools use `wrapToolExecution` for consistent error handling
5. **Input Validation** - Uses Zod schemas with length limits
6. **Cascading Fallback** - Automatic model switching on quota errors

### Standard Tools per Masterplan

| Tool | Description |
|------|-------------|
| `search{Mp}Projects` | Full-text search with type filter |
| `get{Mp}Statistics` | Aggregated stats by type/province |
| `getProvince{Mp}` | Get all items in a province |
| `list{Mp}Types` | List all types with counts |
| `query{Mp}Projects` | Combined filters (province + type + period) |

## Reference Files

- `references/workflow-overview.md` - Detailed workflow guide
- `references/phase-*.md` - Phase-specific instructions
- `references/validation-checklist.md` - **Validation gates for each phase**
- `references/templates/*.ts` - File templates
- `references/ai-utils-reference.md` - Shared AI utilities documentation
- `examples/minerals-866.md` - How minerals was built
- `examples/electricity-768.md` - How electricity was built

## Scripts

- `scripts/scaffold-masterplan.py` - Generate files from templates
- `scripts/upload-to-firebase.py` - Seed Firestore from JSON

## Template Placeholders

| Placeholder | Example |
|-------------|---------|
| `{{MASTERPLAN_ID}}` | forestry |
| `{{MASTERPLAN_ID_PASCAL}}` | Forestry |
| `{{MASTERPLAN_ID_UPPER}}` | FORESTRY |
| `{{MASTERPLAN_NAME_VI}}` | Lâm nghiệp |
| `{{DECISION_ID}}` | QD-999 |
| `{{DECISION_NUMBER}}` | 999 |
| `{{ENTITY_TYPES}}` | ['forests', 'reserves'] |
| `{{PRIMARY_ENTITY}}` | forests |
| `{{PRIMARY_ENTITY_PASCAL}}` | Forest |
| `{{PRIMARY_ENTITY_UPPER}}` | FORESTS |
| `{{PRIMARY_ENTITY_VI}}` | rừng |
| `{{ACCENT_COLOR}}` | emerald |

## Existing Patterns

Reference implementations:
- **Minerals (QH-866)**: `src/components/minerals/`, `src/app/minerals/`
- **Electricity (QH-768)**: `src/components/energy/`, `src/app/electricity/`
- **Seaports (QD-1579)**: `src/components/seaport/`, `src/app/seaports/`

Key shared components:
- `src/components/masterplan/overview-shell.tsx`
- `src/components/masterplan/overview-header.tsx`
- `src/components/masterplan/masterplan-map-shell.tsx`
- `src/lib/masterplan/registry.ts`

Key shared AI utilities:
- `src/lib/ai/utils.ts` - DEFAULTS, wrapToolExecution, normalizeQuery
- `src/lib/ai/province-tools.ts` - resolveProvince tool
- `src/lib/ai/router.ts` - classifyQuery, classifyIntent, needsSummaryContext
- `src/lib/ai/providers.ts` - Model providers (Groq, Cerebras, SambaNova, Gemini 3 Flash Preview, Cohere)
- `src/lib/data/province-groups.ts` - PROVINCE_GROUPS, SHORT_CODE_TO_GROUP

## Shared Map UI Components

### Unified Popup Styles

Import from `src/components/map/ui/popup-styles.ts`:

| Constant | Purpose |
|----------|---------|
| `POPUP_CONTAINER` | Base container (main: w-80, inline: min-w-[240px]) |
| `POPUP_HEADER` | Header with title, close button, draggable option |
| `POPUP_CONTENT` | Content sections (scrollable, fixed, compact) |
| `POPUP_TEXT` | Typography (label, value, valuePrimary, caption) |
| `POPUP_BADGE` | Badges (dot, pill, tag) |
| `POPUP_STAT` | Stat layouts (row, grid) |

**Usage:**
```tsx
import { POPUP_CONTAINER, POPUP_HEADER, POPUP_TEXT } from '@/components/map/ui';

<div className={POPUP_CONTAINER.inline}>
  <div className={POPUP_HEADER.container}>
    <span className={POPUP_HEADER.title}>{name}</span>
  </div>
</div>
```

### Unified Marker Components

Import from `src/components/map/ui/`:

| Component | Purpose | Sizing |
|-----------|---------|--------|
| `MapMarker` | Province/port-level markers | sqrt scaling 24-48px |
| `PointMarker` | Site/terminal markers (circle, diamond) | 8-16px |

**Marker Effects:**
- Shadow: `0 0 12px` (unified across all maps)
- Hover scale: `1.15x`
- Performance: `React.memo` applied

---

## Lessons Learned (Seaport QD-1579)

### Data Extraction Bugs (Phase 1)
| Bug | Impact | Prevention |
|-----|--------|------------|
| Missing coordinates | Empty map (0 markers) | Validate 100% coord coverage |
| Incomplete terminals | 72% blank markers | Extract ALL child entities |

### Data Sync Bugs (Phase 3)
| Bug | Impact | Prevention |
|-----|--------|------------|
| Firestore count mismatch | Stale data, missing entities | Keep upload script expected counts in sync with JSON |
| JSON-Firestore drift | 25 vs 83 terminals | After JSON updates, always re-run upload + verify counts |

### Architecture Bugs (Phase 4)
| Bug | Impact | Prevention |
|-----|--------|------------|
| Standalone page | Lost 6 features | ALWAYS use MasterplanMapShell |
| Missing map controls | No zoom/fullscreen | Include NavigationControl, FullscreenControl |
| Missing layers | No Vietnam boundaries | Include VietnamBoundaryLayers |

### UI Consistency Bugs (Phase 5)
| Bug | Impact | Prevention |
|-----|--------|------------|
| scale-125 hover | Inconsistent UX | Use scale-110 like minerals |
| Mapbox Popup | No connecting line | Use custom positioned popup |
| Gray color | Invisible markers | Use high-contrast colors |
| right-4 position | Stats overlaps controls | Use right-14 |
| No mobile hide | Popup overlaps | Add hidden sm:block |
| Missing search | No search feature | Add SearchAutocomplete |
| 8px dots | Hard to see colors | Use 12px (w-3 h-3) |
| Collapsible popup content | Hidden child entities | Always show ALL items (no collapse) |
| Blue-600 marker color | Confused with Vietnam border | Use distinct colors (violet, amber, not blue) |
| No shared popup styles | Inconsistent look across maps | Import from popup-styles.ts |
| Default mapboxgl white bg | White box behind popup | Add .{class}-popup CSS override |
| Label rows in popup | Too verbose | Use type badges instead |

### Filter Logic Bugs (Phase 5)
| Bug | Impact | Prevention |
|-----|--------|------------|
| Empty array = show all | "Deselect all" shows everything | Use NONE_SELECTED_MARKER pattern |
| Missing type casts | TypeScript errors | Cast to string for marker comparison |

### Number Formatting Bugs (Phase 5)
| Bug | Impact | Prevention |
|-----|--------|------------|
| `.toFixed()` without locale | English decimal format (1.234) | Use central `formatNumber()` utility |
| `.toLocaleString()` without locale | Inconsistent across browsers | Always use 'vi-VN' locale |
| Local `formatNumber` conflicts | Duplicated, inconsistent logic | Import from `@/lib/utils/format-number` |

**Vietnamese Number Format Standard:**
```tsx
// ALWAYS use central utility for ALL number displays
import { formatNumber } from '@/lib/utils/format-number';

// Format: dot=thousands, comma=decimals
formatNumber(1234.5, 1)    // → "1.234,5" (NOT "1,234.5")
formatNumber(398700, 0)    // → "398.700" (NOT "398,700")

// For compact numbers with K/M suffix, create local wrapper:
function formatNumberCompact(n: number): string {
  if (n >= 1000000000) return `${formatNumber(n / 1000000000, 1)}B`;
  if (n >= 1000000) return `${formatNumber(n / 1000000, 1)}M`;
  if (n >= 1000) return `${formatNumber(n / 1000, 1)}K`;
  return formatNumber(n, 0);
}
```

**Files that MUST use formatNumber:**
- All popup components (stats, forecasts, investments)
- All stats cards (overview page)
- All table components (groups, reserves)
- All chart tooltips (treemap, bar chart)
- All map stats overlays

**NONE_SELECTED_MARKER Pattern:**
```tsx
// In filter panel - use '__none__' marker for explicit deselect
import { NONE_SELECTED_MARKER } from '@/lib/constants/filters';

// "Bỏ chọn" button sets to marker, not empty array
onClick={() => onFilterChange({ items: [NONE_SELECTED_MARKER as ItemType] })}

// Check for none mode
const isNoneMode = items.length === 1 && (items[0] as string) === NONE_SELECTED_MARKER;

// In page.tsx filtering logic
if ((filters.items?.[0] as string) === NONE_SELECTED_MARKER) {
  return []; // Hide all
}
```

### Popup Component Rules
1. **Always show ALL child entities** - No collapsing, no "show more" buttons
2. **Use custom positioned popup** - Not Mapbox Popup (for connecting line)
3. **Add hidden sm:block** - Hide popup on mobile to prevent overlap

### Total Effort Saved by Following Skill
| Following Skill | Not Following |
|-----------------|---------------|
| ~8 hours | 20+ hours (15+ fix commits) |

---

## Chatbot Accuracy Testing

### FAQ Test File Structure

Create `tests/chatbot/{mp}-faq.json` for automated chatbot testing:

```json
{
  "masterplan": "forestry",
  "version": "1.0.0",
  "lastUpdated": "2025-12-17",
  "testCases": [
    {
      "id": "F01",
      "category": "counts",
      "question": "Có bao nhiêu rừng sản xuất?",
      "expectedTool": "getForestryStatistics|listForestryTypes",
      "expectedContains": ["10", "rừng"],
      "priority": "high"
    }
  ]
}
```

### Test Case Best Practices (Learned from Seaport)

1. **Accept `none` for context-answerable questions**
   - LLM may answer from injected summary context without calling tools
   - This is VALID behavior - add `|none` to expectedTool
   ```json
   "expectedTool": "getStatistics|none"
   ```

2. **Use flexible keyword matching**
   - Pipe-separated alternatives for multiple valid responses
   ```json
   "expectedContains": ["nhóm 4|group 4|4|số 4"]
   ```

3. **Categories to cover** (minimum 40 cases):
   - `counts` - Aggregate counts (6+ cases)
   - `province` - Province-specific queries (4+ cases)
   - `forecasts` - Future projections (3+ cases)
   - `search` - Keyword search (3+ cases)
   - `details` - Specific entity details (4+ cases)
   - `edge` - Empty results, non-existent entities (2+ cases)
   - `english` - English language queries (3+ cases)
   - `terminal` - Child entity specific queries (4+ cases)
   - `combined` - Multi-filter queries (3+ cases)
   - `ranking` - "Which is largest/most" queries (3+ cases)

4. **Priority levels**: `high` (must pass), `medium` (common), `low` (edge cases)

### Running Tests

```bash
# Run specific masterplan
npx tsx scripts/test-chatbot-accuracy.ts --masterplan=forestry

# Faster testing (5s delay vs 15s default)
TEST_DELAY_MS=5000 npx tsx scripts/test-chatbot-accuracy.ts --masterplan=forestry
```

### Expected Pass Rate

| Rating | Pass Rate | Action |
|--------|-----------|--------|
| ✅ Excellent | ≥93% | Ship to production |
| ⚠️ Acceptable | 85-92% | Review failures, minor fixes |
| ❌ Needs Work | <85% | Debug tool selection/descriptions |

**Note:** Generative AI responses are non-deterministic. A 93%+ stable pass rate is excellent. Do NOT chase 100%.

### Debugging Failed Tests

| Failure Type | Cause | Fix |
|--------------|-------|-----|
| Tool mismatch | LLM used wrong tool | Improve tool descriptions |
| LLM answered from context | Valid behavior | Add `\|none` to expectedTool |
| Keyword mismatch | Response correct, different words | Add alternatives with `\|` |
| Tool not called | Intent not mapped | Update toolset-registry.ts |
