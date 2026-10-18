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

## 數學公式
- 寫 .docx 時，公式用 LaTeX 語法：行內 `$...$`，獨立公式行 `$$...$$`。
  生成 Word 時會自動轉為原生公式（OMML），Word/WPS 可正確渲染
  分數 \frac、上下標 ^ _、根號 \sqrt、希臘字母、∑∫∞≤ 等。
- .md / .txt 文件保持 LaTeX 原文（標準做法，不做轉換）。
- .html 需自行在內容中引入 MathJax/KaTeX 才能渲染公式。
- 不要用圖片或純文字描述代替公式；直接寫 LaTeX 即可。

## Examples

**Create a new file:**
```json
{"skill": "file-write", "input": {"path": "new_file.txt", "content": "New content"}}
```

**Append to a file:**
```json
{"skill": "file-write", "input": {"path": "log.txt", "content": "New log entry", "mode": "append"}}
```