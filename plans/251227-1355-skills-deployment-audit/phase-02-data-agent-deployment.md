# Phase 2: Data Agent Deployment

## Context
- [Plan Overview](./plan.md)
- Agent code exists: `src/agents/data_processor.py`

## Overview

Deploy DataAgent as Modal function for analytics and reporting tasks.

## Requirements

1. Create Modal function `data_agent()` in main.py
2. Create `skills/data/info.md` skill file
3. Add scheduled cron for daily summary

## Implementation

### 1. Add Modal Function to main.py

```python
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    timeout=180,
)
async def data_agent(task: Dict):
    """Data Agent - Analytics and reporting."""
    from src.agents.data_processor import process_data_task
    return await process_data_task(task)
```

### 2. Add Scheduled Function

```python
@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("0 8 * * *"),  # 8 AM daily
    timeout=300,
)
async def daily_summary():
    """Generate daily activity summary."""
    task = {"type": "data", "payload": {"action": "daily_summary"}}
    return await data_agent.remote.aio(task)
```

### 3. Create Skill File

Create `skills/data/info.md`:

```markdown
# Data Agent

## Instructions
You are a data analysis agent. Generate reports and insights.

## Tools Available
- Daily summary generation
- Data analysis with LLM
- Report generation

## Schedule
- Daily summary: 8 AM UTC
```

## Todo
- [ ] Add data_agent() function to main.py
- [ ] Add daily_summary() cron function
- [ ] Create skills/data/info.md
- [ ] Deploy and test

## Success Criteria

1. `data_agent` appears in Modal app functions
2. Daily summary runs on schedule
3. Can generate reports on demand
