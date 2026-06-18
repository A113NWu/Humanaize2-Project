---
name: file-write
description: Write content to a file. Use this when you need to create new files, modify existing files, or save data.
metadata:
  category: file
  risk_level: medium
  requires_approval: true
---

# File Write Skill

## Purpose
Write content to a file on the local filesystem.

## When to Use
- Creating new files
- Modifying existing files
- Saving data or logs
- Writing configuration files

## Input Format
Provide the file path and content as a JSON object:

**Simple format:**
```json
{
  "skill": "file-write",
  "input": {
    "path": "/path/to/file.txt",
    "content": "Hello, World!"
  }
}
```

**Detailed format:**
```json
{
  "skill": "file-write",
  "input": {
    "path": "/path/to/file.txt",
    "content": "Hello, World!",
    "mode": "write",
    "encoding": "utf-8"
  }
}
```

## Parameters
- `path` (required): Absolute path to the file
- `content` (required): Content to write to the file
- `mode` (optional): "write" (overwrite) or "append" (default: "write")
- `encoding` (optional): File encoding (default: "utf-8")

## Output
Returns success status and file path.

## Safety Notes
- Overwrites existing files by default
- Use "append" mode to add to existing files
- Requires approval for safety

## Examples

**Create a new file:**
```json
{"skill": "file-write", "input": {"path": "new_file.txt", "content": "New content"}}
```

**Append to a file:**
```json
{"skill": "file-write", "input": {"path": "log.txt", "content": "New log entry", "mode": "append"}}
```