---
name: shell
description: Execute shell commands on the system. Use this when you need to run system commands, scripts, or programs.
metadata:
  category: system
  risk_level: high
  requires_approval: true
---

# Shell Skill

## Purpose
Execute shell commands on the local system.

## When to Use
- Running system commands (ls, cat, grep, etc.)
- Executing scripts or programs
- Managing files and directories
- System administration tasks

## Input Format
Provide the command to execute as a string or JSON object:

**Simple format:**
```
{"skill": "shell", "input": "ls -la"}
```

**Detailed format:**
```json
{
  "skill": "shell",
  "input": {
    "command": "ls -la",
    "cwd": "/path/to/directory",
    "timeout": 30
  }
}
```

## Parameters
- `command` (required): The shell command to execute
- `cwd` (optional): Working directory for the command
- `timeout` (optional): Maximum execution time in seconds (default: 30)

## Output
Returns command output (stdout and stderr) and execution status.

## Safety Notes
- Commands are executed with user permissions
- Dangerous commands require explicit approval
- Timeout prevents hanging commands
- Output is captured and returned to AI

## Examples

**List files:**
```json
{"skill": "shell", "input": "ls -la"}
```

**Read a file:**
```json
{"skill": "shell", "input": "cat README.md"}
```

**Search for text:**
```json
{"skill": "shell", "input": "grep 'pattern' file.txt"}
```