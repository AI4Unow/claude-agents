---
name: content-hub
description: Visual asset gallery for ClaudeKit Marketing.
category: content
deployment: remote
---

---
name: content-hub
description: Browse assets in visual gallery with filter, search, and preview API. Use when you implement content libraries, develop asset management, or review media.
license: MIT
allowed-tools:
  - Bash
  - Read
---

# Content Hub

Visual asset gallery for ClaudeKit Marketing.

## Quick Start

```bash
# Open gallery
node $HOME/.claude/skills/content-hub/scripts/server.cjs --open

# Rescan assets
node $HOME/.claude/skills/content-hub/scripts/server.cjs --scan

# Stop server
node $HOME/.claude/skills/content-hub/scripts/server.cjs --stop
```

Or use command: `/write:hub`

## Features

- **Gallery Grid**: Thumbnails of assets/ folder
- **Filter/Search**: By type (banners, designs, etc.) and keywords
- **Brand Sidebar**: Displays user's colors and voice from docs/brand-guidelines.md
- **Actions**: Preview, Edit in Claude, Copy path, Generate new
- **R2 Ready**: Manifest schema supports Cloudflare R2 sync (UI disabled)

## API Routes

| Route | Purpose |
|-------|---------|
| `/hub` | Gallery HTML |
| `/api/assets` | Asset list JSON |
| `/api/brand` | Brand context JSON |
| `/api/scan` | Trigger rescan |
| `/file/*` | Serve local files |

## Manifest Schema

Assets stored in `.assets/manifest.json` with R2 fields:

```json
{
  "id": "abc123",
  "path": "banners/hero.png",
  "category": "banner",
  "r2": {
    "status": "local",  // local|pending|synced|error
    "bucket": null,
    "url": null
  }
}
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/server.cjs` | HTTP server entry |
| `scripts/lib/scanner.cjs` | Scan assets directory |
| `scripts/lib/router.cjs` | HTTP routing |
| `scripts/lib/brand-context.cjs` | Extract brand guidelines |

## Integration

**Command**: `/write:hub`

**Related Skills**: brand-guidelines, ai-multimodal, design

**Agents**: content-creator, ui-ux-designer
