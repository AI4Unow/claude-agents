# Phase 4: Skills Volume Sync

## Context
- [Plan Overview](./plan.md)
- Skills volume mounted at `/skills` in Modal

## Overview

Update `init_skills()` to create all agent skill files and ensure volume sync works.

## Requirements

1. Update `init_skills()` to create all 4 skill files
2. Ensure `sync_skills_from_github()` syncs all skills
3. Verify local skills match Modal Volume

## Implementation

### 1. Update init_skills() in main.py

```python
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=60,
)
def init_skills():
    """Initialize skills directory with default info.md files."""
    from pathlib import Path

    skills = {
        "telegram-chat": """# Telegram Chat Agent
## Instructions
You are a helpful AI assistant communicating via Telegram.
- Be concise and friendly
- Use markdown formatting when helpful
- Respond in the same language as the user

## Tools Available
- web_search, get_datetime, run_python, read_webpage, search_memory
""",
        "github": """# GitHub Agent
## Instructions
You are a GitHub automation agent. Handle repository tasks.

## Tools Available
- create_issue, summarize_pr, repo_stats, list_issues
""",
        "data": """# Data Agent
## Instructions
You are a data analysis agent. Generate reports and insights.

## Tools Available
- daily_summary, analyze_data, generate_report
""",
        "content": """# Content Agent
## Instructions
You are a content generation agent.

## Tools Available
- write_content, translate, summarize, rewrite, email_draft
""",
    }

    created = []
    for skill_name, content in skills.items():
        skill_path = Path(f"/skills/{skill_name}/info.md")
        if not skill_path.exists():
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(content)
            created.append(skill_name)

    if created:
        skills_volume.commit()
        return {"status": "initialized", "created": created}

    return {"status": "already_initialized"}
```

### 2. Update Local Skills Directory

Create local skill files to match:
- `skills/github/info.md`
- `skills/data/info.md`
- `skills/content/info.md`

### 3. Verify Sync

```bash
modal run main.py::init_skills
modal volume ls skills-volume
```

## Todo
- [ ] Update init_skills() with all 4 skills
- [ ] Create local skills/github/info.md
- [ ] Create local skills/data/info.md
- [ ] Create local skills/content/info.md
- [ ] Deploy and run init_skills
- [ ] Verify volume contents

## Success Criteria

1. `modal volume ls skills-volume` shows 4 skill directories
2. Each skill has info.md with correct content
3. Local and Modal Volume skills match
