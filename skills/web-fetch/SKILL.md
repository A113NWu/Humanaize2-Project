---
name: web-fetch
description: Fetch content from a web URL. Use this when you need to read the content of a specific webpage or API endpoint.
metadata:
  category: web
  risk_level: low
  requires_approval: false
---

# Web Fetch Skill

## Purpose
Fetch and read content from a specific web URL.

## When to Use
- Reading webpage content
- Fetching API responses
- Downloading documents
- Accessing online resources

## Input Format
Provide the URL as a string or JSON object:

**Simple format:**
```
{"skill": "web-fetch", "input": "https://example.com"}
```

**Detailed format:**
```json
{
  "skill": "web-fetch",
  "input": {
    "url": "https://example.com",
    "timeout": 30,
    "headers": {
      "User-Agent": "Humanaize"
    }
  }
}
```

## Parameters
- `url` (required): The URL to fetch
- `timeout` (optional): Maximum fetch time in seconds (default: 30)
- `headers` (optional): Custom HTTP headers

## Output
Returns the webpage content as text (HTML converted to markdown).

## Examples

**Fetch a webpage:**
```json
{"skill": "web-fetch", "input": "https://docs.python.org"}
```

**Fetch API data:**
```json
{"skill": "web-fetch", "input": {"url": "https://api.example.com/data"}}
```