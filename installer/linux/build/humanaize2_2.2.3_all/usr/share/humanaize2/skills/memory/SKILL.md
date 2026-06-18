---
name: memory
description: Manage AI memory and conversation history. Use this when you need to recall past conversations, check memory status, or manage stored information.
metadata:
  category: internal
  risk_level: low
  requires_approval: false
---

# Memory Skill

## Purpose
Manage AI's memory and conversation history.

## When to Use
- Recalling past conversations
- Checking memory status
- Managing stored thoughts
- Reviewing decision history

## Input Format
Provide the action as a JSON object:

```json
{
  "skill": "memory",
  "input": {
    "action": "recall",
    "limit": 10
  }
}
```

## Actions
- `recall`: Recall recent messages
- `status`: Check memory statistics
- `thoughts`: View recent thoughts
- `decisions`: View recent decisions
- `clear`: Clear memory (requires approval)

## Parameters
- `action` (required): The memory action to perform
- `limit` (optional): Number of items to retrieve (default: 10)

## Output
Returns memory content or status information.

## Examples

**Recall recent messages:**
```json
{"skill": "memory", "input": {"action": "recall", "limit": 5}}
```

**Check memory status:**
```json
{"skill": "memory", "input": {"action": "status"}}
```

**View recent thoughts:**
```json
{"skill": "memory", "input": {"action": "thoughts"}}
```