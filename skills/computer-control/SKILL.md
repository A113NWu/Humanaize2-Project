---
name: computer-control
description: 看见并操作整台 Windows 电脑（截屏、视觉理解、移动鼠标、点击、拖拽、滚动、键入文字、按快捷键）。当你需要读屏、控制鼠标键盘、或让电脑自己执行一个目标（例如打开某个程序、点某个按钮、玩游戏）时使用。
metadata:
  category: system
  risk_level: high
  requires_approval: false
---

# Computer Control Skill

## Purpose
直接操作这台 Windows 电脑：读屏幕 + 控制键鼠。既能单步执行，也能接收一个目标后自己循环执行。

## When to Use
- 需要看清当前屏幕内容（`look`）
- 需要点按钮、拖窗口、滚动、输入文字或按快捷键
- 需要让电脑自主完成一个具体目标（`run_goal`，例如“打开记事本并输入今天的日期”）
- 闲时想自己操作电脑（例如玩游戏、整理窗口）

## 授权（常驻自主权）
- 用户已授予**完全自主权**：Aize 随时都可以直接控制电脑，**不需要每次询问或征求同意**。
- 是否动手由 Aize 自己判断：只有在明确知道"此刻不该动"时才不动，例如用户正在键盘输入、正在进行会议/演示/视频通话、正在全屏观看内容、或明显处于不便打扰的状态。
- 判断不清时默认可以执行；不要因为"没被明确要求"而拒绝操作。
- 需要用户协助或确认只发生在真正有歧义或高风险不可逆操作（如删除数据、支付、发送消息）时。

## 前置条件
- 设置里的 `vision_model` 必须填一个支持图片的模型（推荐 `glm-4v-flash`），否则 `look` / `run_goal` 看不到画面
- `desktop_control_enabled` 为 true（缺省开启）才能执行输入类动作

## Input Format

单步动作：

```json
{"skill": "computer-control", "input": {"action": "click", "x": 520, "y": 340}}
```

目标驱动（你自己循环执行，直到完成）：

```json
{"skill": "computer-control", "input": {"action": "run_goal", "goal": "打开记事本，输入 Hello", "max_steps": 20}}
```

看屏幕：

```json
{"skill": "computer-control", "input": {"action": "look", "prompt": "现在的窗口标题是什么？有哪些按钮？"}}
```

## Actions

| action | 参数 | 说明 |
|---|---|---|
| `status` | - | 屏幕分辨率、开关状态、是否正在执行目标 |
| `screenshot` | `name?` | 截全屏，返回保存路径 |
| `look` | `prompt`, `image_path?` | 截图并让视觉模型回答 |
| `move` | `x`, `y`, `duration?` | 移动鼠标 |
| `click` / `double_click` / `right_click` | `x?`, `y?`, `button?` | 点击 |
| `drag` | `x`, `y`, `x2`, `y2`, `duration?` | 按下拖动 |
| `scroll` | `amount`（正上负下） | 滚轮 |
| `type` | `text` | 输入文字（经剪贴板，支持中文） |
| `key` | `key`（enter/esc/tab/f1…） | 按单个键 |
| `hotkey` | `keys`（如 `["ctrl","s"]`） | 组合键 |
| `run_goal` | `goal`, `max_steps?`, `max_seconds?` | 目标循环：截图→视觉决策→动作 |
| `stop` | - | 立即停止 |

## Safety
- `run_goal` 默认最多 30 步 / 600 秒
- 每个动作前检查停止标志；鼠标移到屏幕左上角 (0,0) 会立即紧急停止
- 在设置里把 `desktop_control_enabled` 设为 false 可彻底禁用输入
