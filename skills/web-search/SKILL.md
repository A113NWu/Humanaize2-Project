---
name: web-search
description: Search the web for information. Results are cleaned (ads/redirects filtered, ranked by relevance), then the top pages are fetched with web-fetch and their text returned.
metadata:
  category: web
  risk_level: low
  requires_approval: false
---

# Web Search Skill

## Purpose
Search the web for current information and facts, then read the top pages.

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
    "language": "zh",
    "fetch_pages": 2,
    "fetch_max_chars": 3000
  }
}
```

## Parameters
- `query` (required): The search query
- `num_results` (optional): Number of results to return (default: 5)
- `language` (optional): Language restriction (e.g., "en", "zh")
- `fetch_pages` (optional): How many top pages to fetch with web-fetch (default: 2, 0 disables)
- `fetch_max_chars` (optional): Max characters kept per fetched page (default: 3000)

## Output
Returns results with title, URL, snippet, plus `content` (正文摘要) and `fetched` for pages that were fetched.
Results are deduplicated and ranked; 广告 / 跳转链接 / 与查询无关的条目会被丢弃。
If nothing relevant is found, `count` is 0 and a `note` suggests trying a more specific query.

## Examples

**Search for documentation:**
```json
{"skill": "web-search", "input": "TensorFlow documentation"}
```

**Search for news:**
```json
{"skill": "web-search", "input": {"query": "AI news 2026", "num_results": 10}}
```