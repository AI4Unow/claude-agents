# Terminal/CLI Patterns for Chat Bots

## Command Parsing Patterns

### Slash Commands
```
/skill <name> <task>     # Direct skill invocation
/skill:planning "task"   # Alternative syntax
/skills                  # List all skills
/skills:dev              # Filter by category
```

### Argument Parsing
- Positional: `/translate hello world`
- Named: `/skill --name=planning --mode=simple`
- Quoted strings: `/exec "multi word argument"`

## Interactive Menus

### Skill Selection Flow
```
User: /skills
Bot: [Inline Keyboard]
     [planning] [debugging] [research]
     [code-review] [more...]

User: [clicks planning]
Bot: Enter task for planning skill:

User: Create auth system plan
Bot: [executes skill, returns result]
```

### Mode Selection
```
User: /skill planning "auth plan"
Bot: Select execution mode:
     [Simple] [Routed] [Evaluated]
```

## Session Management

### Context Preservation
- Store active skill in Firebase per user
- Multi-turn conversations within skill
- `/cancel` to exit current context

### State Machine
```
IDLE → SKILL_SELECT → TASK_INPUT → EXECUTING → RESULT
                                        ↓
                                   FOLLOW_UP
```

## Output Formatting

### Terminal-like Display
```
$ skill: planning
$ mode: simple
$ task: Create auth plan

[Executing...]

--- Result ---
1. Design user model
2. Implement JWT tokens
...

Duration: 3.2s | Tokens: 1,234
```

### Long Output Handling
- Paginate with "Show more" buttons
- File attachment for very long outputs
- Summary + full in expandable section

## Error Handling

### User Feedback
- Clear error messages
- Retry buttons
- Fallback suggestions

### Example
```
Error: Skill 'planing' not found.
Did you mean: planning?
[Use planning] [List skills]
```

## Recommended Pattern for This Project

1. `/skill <name> <task>` - Direct execution
2. `/skills` - Show skill menu with inline keyboard
3. `/mode <simple|routed|evaluated>` - Set default mode
4. Regular messages - Route to active skill or agentic loop
5. Callback queries - Handle button clicks for menus
