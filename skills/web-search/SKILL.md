---
name: web-search
description: Search the web for information. Use this when you need to find current information, research topics, or look up facts online.
metadata:
  category: web
  risk_level: low
  requires_approval: false
---

# Web Search Skill

## Purpose
Search the web for current information and facts.

## When to Use
- Finding current news or events
- Researching topics
- Looking up facts or definitions
- Finding documentation or tutorials

## Input Format
Provide the search query as a string or JSON object:

**Simple format:**
```
{"skill": "web-search", "input": "Python tutorial"}
```

**Detailed format:**
```json
{
  "skill": "web-search",
  "input": {
    "query": "Python tutorial",
    "num_results": 5,
    "language": "en"
  }
}
```

## Parameters
- `query` (required): The search query
- `num_results` (optional): Number of results to return (default: 5)
- `language` (optional): Language restriction (e.g., "en", "zh")

## Output
Returns search results with titles, URLs, and snippets.

## Examples

**Search for documentation:**
```json
{"skill": "web-search", "input": "TensorFlow documentation"}
```

**Search for news:**
```json
{"skill": "web-search", "input": {"query": "AI news 2026", "num_results": 10}}
```