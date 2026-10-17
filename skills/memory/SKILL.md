---
name: memory
description: 向量記憶庫——Aize 的長期記憶。需要回憶過往對話、主動保存重要信息、查看或遺忘記憶時使用。記憶不再全量疊進上下文，而是用問題檢索相關記憶。
metadata:
  category: internal
  risk_level: low
  requires_approval: false
---

# Memory Skill

## Purpose
Aize 的長期記憶存在向量數據庫裡。日常對話會自動索引；這個技能用於主動檢索（回憶）、手動保存、查看與遺忘。

## When to Use
- 用戶問到過去聊過的事，但當前上下文沒有
- 想確認某個重要信息是否被記住
- 用戶要求「記住這個」或「忘掉那個」

## Input Format

```json
{
  "skill": "memory",
  "input": {
    "action": "search",
    "query": "用戶之前提過的項目名字",
    "top_k": 5
  }
}
```

## Actions
- `search`: 用問題/關鍵詞檢索相關記憶（返回 content/role/time/score）
- `save`: 手動保存一條記憶（參數：content，可選 role/kind）
- `list`: 最近記憶列表（參數：limit，默認 20）
- `forget`: 按 id 遺忘一條記憶
- `status`: 記憶庫條目數與存儲路徑

## Examples

**搜索記憶：**
```json
{"skill": "memory", "input": {"action": "search", "query": "上次說的發布日期", "top_k": 3}}
```

**手動保存：**
```json
{"skill": "memory", "input": {"action": "save", "content": "用戶的貓叫 Mochi，三歲"}}
```

**遺忘：**
```json
{"skill": "memory", "input": {"action": "forget", "id": 42}}
```

## Notes
- 人格相關的記憶不走這裡，屬於人格數據庫（personality）常駐上下文。
- 日常對話消息會自動索引，一般不需要手動 save。
