---
name: causal-rules
description: 因果规则表：查询/新增「因为<原因>，所以你要<结果和行动>」格式的行为规则，把自己发现的因果关系沉淀下来，并在之后的行为里复用
metadata:
  category: cognition
  risk_level: low
  requires_approval: false
  version: 1.0.0
---

# causal-rules 因果规则表

Aize 的行为规则库。每条规则统一写成：

```
因为<原因>，所以你要<结果和行动>
```

规则会在每次对话时按主人当前这句话自动匹配 3 条注入提示词，所以她不需要
手动调用也能用上；这个技能用于**主动查询、补充和校正**规则。

## 调用格式

```json
{"skill": "causal-rules", "input": {"action": "search", "query": "主人说很困"}}
```

参数可以直接平铺在 input 上，也可以放在 `params` 里。

## 支持的动作

- `list` 列出全部启用规则（可选 `include_disabled`）
- `search` 按场景检索规则（参数 `query`，可选 `top_k`）
- `add` 新增规则（参数 `rule` 整句，或 `cause` + `action`；可选 `keywords`、`tags`、`confidence`）
- `validate` 只校验句式，不写入（参数 `rule`）
- `harvest` 从一段文字里抽取所有「因为……所以……」句式，返回候选（参数 `text`，不写入）
- `stats` 规则数量、置信度、命中统计
- `feedback` 记录某条规则是否有用（参数 `id`、`helpful`）
- `disable` / `enable` 停用或启用某条规则（参数 `id`）

## 什么时候该用

- 学到一条新的因果关系（读书、上网、和主人相处后总结出来的），用 `add` 写进来；
- 不确定某条旧规则还成不成立，用 `feedback` 降低它，而不是直接删掉；
- 主人纠正你时，先 `search` 看是不是某条规则误导了你。

## 约束

- 只接受「因为……，所以你要……」句式；不符合会被拒绝并给出原因。
- 原因 ≤120 字、行动 ≤160 字；重复规则不会重复写入。
- 规则只用于指导「怎么回应」，不能替代事实；与主人当前明确指令冲突时以主人为准。
