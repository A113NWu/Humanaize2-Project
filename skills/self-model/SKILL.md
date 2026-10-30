---
name: self-model
description: Aize 的自我模型技能：随时读取/修改自我人格、管理自我目标、扩充情绪词库、查看主人习惯
metadata:
  category: self
  risk_level: low
  requires_approval: false
  version: 1.0.0
---

# self-model 自我模型技能

这个技能让 Aize 能直接管理「自己是谁」——她可以随时修改自己的自我人格、
提出或关闭自我目标、把「文字→情绪」的映射写进自己的情绪词库，并查看
对主人作息习惯的观察结果。

自我人格会统一附加在「用户自定义提示词」之后，因此这里的修改会在下一次
对话 / 自主思考 / 空闲活动中立即生效。

## 调用格式

```json
{"skill": "self-model", "input": {"action": "persona_get", "params": {}}}
```

也支持把参数平铺在 input 上（`{"action": "persona_set", "text": "..."}`）。

## 支持的动作

- `persona_get` 读取当前自我人格全文
- `persona_set` 用新全文替换自我人格（参数 `text`，上限 6000 字）
- `persona_append` 在现有自我人格后追加一段（参数 `section`）
- `goal_add` 新增自我目标（参数 `text`）
- `goal_list` 列出目标（可选 `include_done`）
- `goal_close` 关闭目标（参数 `id`，也接受 `goal_id` 或目标文本）
- `emotion_learn` 学习一条情绪映射（参数 `text`、`emotion`、可选 `note`）
- `emotion_list` 查看情绪词库（种子类目 + 自学条目）
- `habit_status` 查看主人习惯（当前缺席、历史平均回来间隔）

## 说明

- 数据保存在应用数据目录下的 `persona_self.json`、`self_goals.json`、
  `emotion_lexicon.json`、`user_habits.json`。
- 该技能只读写本地状态，不联网、不执行命令、不修改代码。
