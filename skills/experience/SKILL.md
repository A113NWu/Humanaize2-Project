---
name: experience
description: Aize 的經驗數據庫（類似向量數據庫）：把溝通中總結出的思考方式、判斷策略、見聞保存起來，相似的新經驗會自動覆蓋舊經驗；回答前也可檢索過往經驗輔助判斷
metadata:
  category: memory
  risk_level: low
  requires_approval: false
  version: 1.0.0
---

# 經驗數據庫技能

Aize 的長期經驗庫，**側重保存「思考方式」**——即「遇到某類情況時我是怎麼想的、怎麼判斷的」。

## 使用時機
- 總結出一條可複用的**思考方式 / 判斷方法 / 排查思路**時，立即 `save`（kind=thinking）
- 獲得值得記住的**見聞、事實、主人的偏好**時 `save`（kind=observation 或 fact）
- 同一話題有了新的理解時再次 `save`：相似經驗會自動覆蓋舊版本，不用手動刪
- 遇到似曾相識的問題時先 `search` 回顧過往經驗再回答

## 調用格式

```json
{"skill": "experience", "input": {"action": "save", "params": {"text": "主人問系統狀態類問題時，應該先實際執行命令拿到數據再回答，不要只給教程", "kind": "thinking", "tags": ["回答策略"]}}}
```

```json
{"skill": "experience", "input": {"action": "search", "params": {"query": "怎麼回答系統檢查類問題", "top_k": 3}}}
```

```json
{"skill": "experience", "input": {"action": "list"}}
```

```json
{"skill": "experience", "input": {"action": "forget", "params": {"id": 12}}}
```

## 說明
- kind 可選 `thinking`（思考方式，預設）/ `observation`（見聞）/ `fact`（事實）
- save 返回 `overwritten` 表示覆蓋了舊經驗，`created` 表示新增
- text 要寫成完整一句話的經驗本身，不要寫「我決定保存…」這類過程描述
