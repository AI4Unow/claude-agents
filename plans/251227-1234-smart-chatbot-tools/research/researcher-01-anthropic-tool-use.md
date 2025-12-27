# Anthropic Claude API Tool Use Research

## Overview
Claude's tool use enables AI to interact with external systems via structured function calling.

## Tool Definition Schema
```python
tools = [{
    "name": "tool_name",
    "description": "Clear description of what tool does",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
            "param2": {"type": "number", "description": "..."}
        },
        "required": ["param1"]
    }
}]
```

## Request/Response Format

### Request
```python
response = client.messages.create(
    model="claude-3-5-sonnet-20240620",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "..."}]
)
```

### Response with Tool Call
```json
{
  "content": [
    {"type": "text", "text": "I'll help with that."},
    {"type": "tool_use", "id": "toolu_xxx", "name": "tool_name", "input": {...}}
  ],
  "stop_reason": "tool_use"
}
```

## Agentic Loop Pattern
```python
messages = [{"role": "user", "content": user_input}]

while True:
    response = client.messages.create(
        model=model, tools=tools, messages=messages, max_tokens=4096
    )

    # Check stop reason
    if response.stop_reason == "end_turn":
        break  # Done

    if response.stop_reason == "tool_use":
        # Append assistant response to history
        messages.append({"role": "assistant", "content": response.content})

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result)
                })

        # Append tool results as user message
        messages.append({"role": "user", "content": tool_results})
```

## Best Practices

1. **Clear tool descriptions** - Help Claude understand when to use each tool
2. **Validate inputs** - Check tool inputs before execution
3. **Error handling** - Return error messages in tool_result for Claude to handle
4. **Limit iterations** - Set max loop count to prevent infinite loops
5. **Token efficiency** - Keep tool results concise

## Error Handling
```python
try:
    result = execute_tool(name, input)
    return {"type": "tool_result", "tool_use_id": id, "content": result}
except Exception as e:
    return {"type": "tool_result", "tool_use_id": id, "content": f"Error: {e}", "is_error": True}
```

## Key Considerations
- Tool results must include `tool_use_id` matching the request
- Multiple tools can be called in parallel in single response
- Keep system prompts focused on tool usage guidance
