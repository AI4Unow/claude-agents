# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Modal.com Self-Improving Agents** using the **II Framework (Information & Implementation)**. Multi-agent system where agents read instructions from Modal Volume, execute tasks, and rewrite their own instructions based on experience.

See [docs/project-overview-pdr.md](docs/project-overview-pdr.md) for full requirements.

## Status

**Phase:** Planning - No code implemented yet

## Build & Development Commands

```bash
# Install Modal CLI
pip install modal
modal setup

# Deploy to Modal
modal deploy main.py

# Local development
modal serve main.py

# View logs
modal app logs claude-agents
```

## Architecture

See [docs/system-architecture.md](docs/system-architecture.md) for full architecture.

**Key Pattern:** Each skill = `.md` (Information) + `.py` (Implementation)
- `.md` → Modal Volume (mutable, self-improving)
- `.py` → Modal Server (immutable after deploy)

**Stack:** Modal.com, Firebase, Qdrant Cloud, Anthropic Claude, Vercel Edge

## Project Structure

```
./
├── docs/                          # Documentation
│   ├── project-overview-pdr.md    # Product requirements
│   ├── system-architecture.md     # Architecture diagrams
│   ├── code-standards.md          # Coding conventions
│   └── codebase-summary.md        # Current status
├── plans/                         # Implementation plans
│   └── 251226-1500-modal-claude-agents/
└── README.md
```

## Code Standards

See [docs/code-standards.md](docs/code-standards.md) for conventions.
