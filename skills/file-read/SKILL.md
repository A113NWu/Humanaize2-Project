---
name: file-read
description: Read content from a file. Use this when you need to read existing files, check file contents, or analyze code.
metadata:
  category: file
  risk_level: low
  requires_approval: false
---

# File Read Skill

## Purpose
Read content from a file on the local filesystem.

## When to Use
- Reading source code files
- Checking configuration files
- Analyzing documents
- Viewing logs or data files

## Input Format
Provide the file path as a string or JSON object:

**Simple format:**
```
{"skill": "file-read", "input": "/path/to/file.txt"}
```

**Detailed format:**
```json
{
  "skill": "file-read",
  "input": {
    "path": "/path/to/file.txt",
    "limit": 100,
    "offset": 0
  }
}
```

## Parameters
- `path` (required): Absolute path to the file
- `limit` (optional): Maximum number of lines to read (default: 2000)
- `offset` (optional): Starting line number (default: 0)

## Output
Returns the file content with line numbers.

## Examples

**Read a Python file:**
```json
{"skill": "file-read", "input": "main.py"}
```

**Read specific lines:**
```json
{"skill": "file-read", "input": {"path": "config.json", "limit": 50}}
```