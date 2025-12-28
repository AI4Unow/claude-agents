# Claude Agents SDK Integration with II Framework

## Problem Statement

Integrate Claude Agents SDK philosophy and workflow patterns into the existing II Framework architecture to create a production-ready agent system with:
- Intelligent skill routing
- Multi-agent orchestration
- Quality evaluation loops
- Sequential task chaining

## Claude Agents SDK Philosophy

### Core Principles (from Anthropic)

| Principle | Description |
|-----------|-------------|
| Simplicity First | Start with simple patterns, add complexity only when needed |
| Agentic Loops | Agent = LLM + Tools + Loop (call LLM → use tools → repeat) |
| Tool Use as Actions | Tools are the agent's way to affect the world |
| Minimal State | Keep state simple; prefer stateless where possible |
| Human-in-the-Loop | Design for human oversight at critical points |

### Official Workflow Patterns

1. **Prompt Chaining** - Sequential LLM calls with output→input
2. **Routing** - Classify intent, route to specialized handler
3. **Parallelization** - Multiple LLMs in parallel, aggregate
4. **Orchestrator-Workers** - Main agent delegates to specialists
5. **Evaluator-Optimizer** - Generate→Evaluate→Improve loop

## Integrated Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 II FRAMEWORK + CLAUDE AGENTS SDK                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT                                                                       │
│    │                                                                         │
│    ▼                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  1. ROUTING LAYER                                                      │  │
│  │     User Request → Intent Classifier → Skill Router (Qdrant semantic) │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│    │                                                                         │
│    ▼                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  2. ORCHESTRATOR                                                       │  │
│  │     • Decompose complex tasks                                          │  │
│  │     • Delegate to skill workers                                        │  │
│  │     • Synthesize outputs                                               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│    │                                                                         │
│    ├─────────────────────┬─────────────────────┐                            │
│    ▼                     ▼                     ▼                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ Skill Worker │  │ Skill Worker │  │ Skill Worker │   PARALLEL           │
│  │ (info.md)    │  │ (info.md)    │  │ (info.md)    │                      │
│  │ + tools      │  │ + tools      │  │ + tools      │                      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                      │
│         │                 │                 │                               │
│         └────────────┬────┴─────────────────┘                               │
│                      ▼                                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  3. PROMPT CHAINING (if sequential)                                    │  │
│  │     Output₁ → Skill₂ → Output₂ → Skill₃ → Final                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                      │                                                       │
│                      ▼                                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  4. EVALUATOR-OPTIMIZER                                                │  │
│  │     Output → Evaluate → Score < 0.8? → Improve → Loop (max 3x)        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                      │                                                       │
│                      ▼                                                       │
│  OUTPUT + Memory Update (Firebase temporal + Qdrant + info.md)              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. SkillRouter (Routing Pattern)

```python
class SkillRouter:
    """Route requests to skills using Qdrant semantic search."""

    async def route(self, request: str) -> List[Skill]:
        matches = await self.qdrant.search("skills", embed(request), limit=3)
        return [self.registry.get_full(m.payload["name"]) for m in matches]
```

### 2. Orchestrator (Orchestrator-Workers Pattern)

```python
class Orchestrator:
    """Decompose, delegate, synthesize."""

    async def execute(self, task: str, context: dict) -> str:
        subtasks = await self.decompose(task)
        results = await asyncio.gather(*[
            self.execute_worker(skill, subtask)
            for subtask, skill in zip(subtasks, await self.route_all(subtasks))
        ])
        return await self.synthesize(results)
```

### 3. ChainedExecution (Prompt Chaining)

```python
class ChainedExecution:
    """Sequential skill execution with output→input passing."""

    async def execute_chain(self, skills: List[str], input: str) -> str:
        for skill_name in skills:
            input = await self.execute_skill(skill_name, input)
        return input
```

### 4. EvaluatorOptimizer (Evaluator-Optimizer)

```python
class EvaluatorOptimizer:
    """Generate, evaluate, improve loop."""

    async def generate_with_evaluation(self, skill: Skill, task: str) -> str:
        for _ in range(3):
            output = await self.execute_skill(skill, task)
            eval = await self.evaluate(output, task)
            if eval["score"] >= 0.8:
                return output
            task = f"{task}\n\nFeedback: {eval['feedback']}"
        return output
```

### 5. AgentLoop (SDK Tool Use Pattern)

```python
async def agent_loop(instructions: str, tools: List, task: str) -> str:
    """Standard Anthropic agent loop with tool use."""
    messages = [{"role": "user", "content": task}]

    while True:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            system=instructions,
            messages=messages,
            tools=tools,
        )

        if response.stop_reason == "tool_use":
            tool_result = await execute_tool(response.content)
            messages.extend([
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_result}
            ])
        else:
            return response.content[0].text
```

## Integration with Memory Spectrum

| Layer | Role in Agent Patterns |
|-------|------------------------|
| Working Memory | Current conversation, active tool outputs |
| Short-term (info.md) | Per-skill preferences, recent patterns |
| Long-term (Firebase) | Execution logs, learned decisions (temporal) |
| Semantic (Qdrant) | Skill routing, knowledge search, error patterns |

## File Structure

```
agents/
├── src/
│   ├── core/
│   │   ├── orchestrator.py      # Orchestrator class
│   │   ├── router.py            # SkillRouter class
│   │   ├── chain.py             # ChainedExecution class
│   │   ├── evaluator.py         # EvaluatorOptimizer class
│   │   └── agent_loop.py        # Standard agent loop
│   ├── agents/
│   │   ├── base.py              # BaseAgent with patterns
│   │   └── ...                  # Specialized agents
│   ├── skills/
│   │   └── registry.py          # SkillRegistry with progressive disclosure
│   └── services/
│       ├── firebase.py          # Firebase temporal
│       └── qdrant.py            # Qdrant semantic
└── skills/
    └── {skill-name}/
        └── info.md              # Skill instructions + memory
```

## Execution Modes

| Mode | Pattern | When to Use |
|------|---------|-------------|
| Simple | Direct skill execution | Single, clear task |
| Routed | Routing → Skill | Unknown best skill |
| Orchestrated | Orchestrator → Workers | Complex, decomposable |
| Chained | Skill₁ → Skill₂ → ... | Sequential dependencies |
| Evaluated | Generate → Evaluate → Loop | Quality-critical output |

## Success Metrics

| Metric | Target |
|--------|--------|
| Routing accuracy | >90% correct skill selection |
| Orchestrator efficiency | Correct decomposition 85%+ |
| Evaluation improvement | 20%+ quality gain per iteration |
| Chain completion | 95%+ successful chains |

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Routing method | Qdrant semantic | Progressive disclosure aligned |
| Worker isolation | Separate context per worker | Prevent context pollution |
| Evaluation model | Same model as generator | Simplicity, cost |
| Chain storage | Firebase temporal | Track intermediate results |
| Tool format | Anthropic tool_use | SDK native |

## Unresolved Questions

1. Should orchestrator use same or smaller model than workers?
2. Evaluation criteria standardization across skills?
3. Maximum chain length before degradation?
4. Parallel execution limits on Modal?

## Next Steps

1. Update Phase 1 with agent patterns
2. Implement SkillRouter with Qdrant
3. Implement Orchestrator class
4. Implement ChainedExecution
5. Implement EvaluatorOptimizer
6. Integration tests for all patterns

## References

- [Building Effective Agents](https://anthropic.com/research/building-effective-agents) - Anthropic
- [Anthropic Cookbook - Agent Patterns](https://github.com/anthropics/anthropic-cookbook/tree/main/patterns/agents)
- [Anthropic SDK Python](https://github.com/anthropics/anthropic-sdk-python)
