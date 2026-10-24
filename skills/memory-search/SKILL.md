---
name: memory-search
description: 搜尋長期記憶庫（以往對話、事實、主人的偏好）。需要回憶之前聊過什麼、主人提過的要求、或某件事的細節時使用。
metadata:
  category: memory
  risk_level: low
  requires_approval: false
  builtin: true
---

# Memory Search

## Purpose
從長期記憶庫按關鍵詞檢索相關片段。每句話都會寫入記憶庫，但記憶不會自動塞進上下文，需要時自己搜。

## When to Use
- 主人提到「之前」「上次」「我跟你說過」之類的回指
- 需要確認主人的偏好、要求、約定
- 當前的問題依賴早前對話的細節
- 不確定某件事是否聊過

## Usage
```json
{"skill": "memory-search", "input": {"query": "關鍵詞", "top_k": 5}}
```

## Output
返回命中的記憶片段清單（時間、說話人、內容），無命中時返回「記憶庫裡沒有找到相關內容」。
