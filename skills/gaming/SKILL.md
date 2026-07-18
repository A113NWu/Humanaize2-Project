# Gaming Skill - AI游戏技能

## 功能介绍

Humanaize Gaming Skill 是一个让AI能够通过截屏和控制键鼠来玩电脑游戏的技能。

### 核心功能

1. **屏幕捕获** - 获取游戏画面进行分析
2. **键鼠控制** - 控制游戏角色移动、跳跃、攻击等
3. **多层死亡检测** - 支持文字检测、血条监控、画面突变、LLM视觉判断四种检测方式
4. **记忆路由** - 失败记录到经验模块，正常记录到记忆模块
5. **GAN禁用** - 游戏时自动关闭GAN节省算力
6. **紧急停止** - 快捷键强制终止
7. **游戏配置文件** - 支持不同游戏的自定义操作映射和死亡检测策略

## 使用方法

### 通过命令行启动GUI配置

```bash
# 通过技能管理器启动GUI
humanaize2 skills -startgui gaming

# 启用游戏技能（自动加载配置）
humanaize2 skills -enable gaming
```

### 通过技能调用启动GUI

```json
{"skill": "gaming", "input": {"action": "startgui"}}
```

### 开始游戏

```json
{"skill": "gaming", "input": {"action": "start", "fps": 5}}
```

### 指定游戏配置开始

```json
{"skill": "gaming", "input": {"action": "start", "fps": 5, "game_name": "minecraft"}}
```

### 开始以撒的结合（无文字提示的游戏）

```json
{"skill": "gaming", "input": {"action": "start", "fps": 5, "game_name": "binding_of_isaac"}}
```

### 停止游戏

```json
{"skill": "gaming", "input": {"action": "stop"}}
```

### 获取可用配置

```json
{"skill": "gaming", "input": {"action": "get_profiles"}}
```

### 加载配置文件

```json
{"skill": "gaming", "input": {"action": "load_profile", "profile": "starcraft"}}
```

### 手动控制

```json
{"skill": "gaming", "input": {"action": "move", "direction": "left"}}
{"skill": "gaming", "input": {"action": "jump"}}
{"skill": "gaming", "input": {"action": "attack"}}
```

### 分析画面

```json
{"skill": "gaming", "input": {"action": "analyze"}}
```

### 检测死亡状态

```json
{"skill": "gaming", "input": {"action": "detect_death"}}
```

### 检测当前游戏窗口并匹配配置

```json
{"skill": "gaming", "input": {"action": "detect_game"}}
```

### 获取当前活动窗口标题

```json
{"skill": "gaming", "input": {"action": "get_window_title"}}
```

### 检测时间限制状态

```json
{"skill": "gaming", "input": {"action": "detect_time_limit"}}
```

## 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| action | string | 操作类型（start/stop/move/jump/attack/analyze等） |
| fps | int | 帧率（1-30，默认5） |
| game_name | string | 游戏配置文件名（不带.json后缀） |
| profile | string | 配置文件名（用于load_profile） |
| direction | string | 移动方向（left/right/up/down） |
| x | int | 鼠标点击X坐标 |
| y | int | 鼠标点击Y坐标 |

## 紧急停止

按 **Ctrl+Shift+Q** 或 **ESC** 键可以立即终止所有游戏操作。

## 死亡检测机制

### 四种检测方式

| 检测方式 | 说明 | 适用场景 |
|---------|------|---------|
| **text** | OCR文字识别 | 游戏显示"Game Over"、"You Died"等文字 |
| **health_bar** | 血条颜色监控 | 游戏有血条，死亡时血条清空 |
| **scene_change** | 画面突变检测 | 死亡时画面切换到结算界面 |
| **visual_cues** | LLM视觉判断 | 兜底方案，让AI分析画面判断死亡 |

### 检测优先级

检测按照配置的 `enabled_methods` 顺序执行，任一方式检测到死亡即判定失败。

## GUI配置界面

游戏技能提供了可视化配置界面，支持创建和管理游戏配置。

### 界面功能

1. **配置列表** - 左侧显示所有已安装的游戏配置，支持新建、删除、保存
2. **激活触发** - 设置窗口标题匹配规则，当检测到指定游戏窗口时自动加载配置
3. **操作映射** - 添加、编辑、删除游戏操作，支持键盘按键录制和鼠标点击配置
4. **时间限制** - 配置关卡时间限制、紧急阈值和警告关键词
5. **死亡检测** - 配置四种死亡检测方法：文字检测、血条检测、画面突变、视觉线索

### 快捷键

- **检测窗口标题** - 点击"检测窗口标题"按钮，自动获取当前活动窗口标题
- **录制按键** - 点击"录制按键"后5秒内按下的按键会被记录
- **选择血条区域** - 截取屏幕并手动框选血条区域
- **ESC键** - 在区域选择窗口中按ESC取消选择

## 激活触发配置

激活触发允许系统自动检测游戏窗口并加载对应配置。

### 配置字段

| 字段 | 类型 | 说明 |
|------|------|------|
| trigger.window_title | string | 窗口标题匹配字符串 |
| trigger.match_mode | string | 匹配模式：contains（包含）、equals（等于）、regex（正则） |

### 匹配模式说明

- **contains** - 窗口标题包含指定字符串即匹配（默认）
- **equals** - 窗口标题完全相等才匹配
- **regex** - 使用正则表达式匹配窗口标题

### 示例

```json
"trigger": {
    "window_title": "Minecraft",
    "match_mode": "contains"
}
```

当检测到活动窗口标题包含"Minecraft"时，自动加载该配置。

## 时间限制配置

时间限制检测允许系统监控游戏中的时间限制，适用于像武士零（Katana ZERO）这类每关有时间限制的游戏。

### 配置字段

| 字段 | 类型 | 说明 |
|------|------|------|
| time_limit.enabled | boolean | 是否启用时间限制检测 |
| time_limit.total_time | number | 关卡总时间（秒） |
| time_limit.urgency_threshold | number | 紧急阈值（0-100），剩余时间百分比低于此值时触发紧急状态 |
| time_limit.action_on_timeout | string | 超时时执行的动作（如restart） |
| time_limit.warning_messages | array | 时间警告关键词列表（OCR检测） |

### 工作原理

1. **时间追踪** - 游戏开始时记录开始时间，根据配置的总时间计算剩余时间
2. **紧急状态检测** - 当剩余时间百分比低于紧急阈值时，记录紧急状态并在日志中警告
3. **超时判定** - 当剩余时间为0时，判定为游戏失败，记录到经验模块
4. **OCR检测** - 通过识别屏幕上的时间警告文字（如"time"、"warning"）触发警告

### 示例

```json
"time_limit": {
    "enabled": true,
    "total_time": 120,
    "urgency_threshold": 30,
    "action_on_timeout": "restart",
    "warning_messages": ["time", "warning", "hurry"]
}
```

## 游戏配置文件

游戏配置文件存放在 `skills/gaming/profiles/` 目录下，每个游戏对应一个JSON文件。

### 配置文件格式

```json
{
    "game_name": "游戏名称",
    "description": "游戏描述",
    "trigger": {
        "window_title": "游戏窗口标题",
        "match_mode": "contains"
    },
    "controls": [
        {
            "name": "操作显示名称",
            "action": "操作标识符",
            "type": "key/mouse_click/mouse_move",
            "keys": ["按键列表"],
            "button": "left/right/middle",
            "description": "操作说明"
        }
    ],
    "death_detection": {
        "enabled_methods": ["text", "health_bar", "scene_change", "visual_cues"],
        "text": {
            "keywords": ["死亡关键词列表"],
            "enabled": true
        },
        "health_bar": {
            "enabled": true,
            "region": {"x": 5, "y": 90, "width": 15, "height": 8},
            "empty_color": [0, 0, 0],
            "threshold": 50
        },
        "scene_change": {
            "enabled": true,
            "threshold": 30
        },
        "visual_cues": {
            "enabled": true,
            "confidence_threshold": 0.7
        }
    },
    "ui_regions": {},
    "tips": ["游戏提示"]
}
```

### death_detection 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| enabled_methods | array | 启用的检测方法列表，按优先级排序 |
| text.keywords | array | 死亡关键词列表（英文小写） |
| text.enabled | boolean | 是否启用文字检测 |
| health_bar.enabled | boolean | 是否启用血条检测 |
| health_bar.region | object | 血条区域坐标（百分比或像素） |
| health_bar.empty_color | array | 空血条颜色（RGB） |
| health_bar.threshold | number | 颜色差异阈值（0-255） |
| scene_change.enabled | boolean | 是否启用画面突变检测 |
| scene_change.threshold | number | 像素变化百分比阈值（0-100） |
| visual_cues.enabled | boolean | 是否启用LLM视觉判断 |
| visual_cues.confidence_threshold | number | LLM置信度阈值（0-1） |

### 内置配置文件

| 配置文件 | 适用游戏 | 死亡检测方式 |
|---------|---------|-------------|
| `generic.json` | 通用游戏 | text + visual_cues |
| `minecraft.json` | Minecraft | text + scene_change + visual_cues |
| `starcraft.json` | 星际争霸 | text + scene_change + visual_cues |
| `2048.json` | 2048 | text + visual_cues |
| `binding_of_isaac.json` | 以撒的结合 | scene_change + health_bar + visual_cues |

### 创建自定义配置文件

1. 在 `skills/gaming/profiles/` 目录下创建新的JSON文件
2. 按照上面的格式定义游戏操作和死亡检测策略
3. 使用 `{"skill": "gaming", "input": {"action": "load_profile", "profile": "文件名"}}` 加载

#### 示例：无文字提示的游戏配置

```json
{
    "game_name": "MyGame",
    "description": "没有文字提示的游戏",
    "controls": [...],
    "death_detection": {
        "enabled_methods": ["scene_change", "health_bar", "visual_cues"],
        "text": {
            "enabled": false
        },
        "health_bar": {
            "enabled": true,
            "region": {"x": 10, "y": 95, "width": 20, "height": 5},
            "empty_color": [30, 30, 30],
            "threshold": 40
        },
        "scene_change": {
            "enabled": true,
            "threshold": 35
        },
        "visual_cues": {
            "enabled": true,
            "confidence_threshold": 0.75
        }
    }
}
```

## 依赖库

- pyautogui - 键鼠控制
- pillow - 屏幕捕获
- opencv-python - 图像处理
- numpy - 数值计算
- pytesseract - OCR文本识别
- keyboard - 快捷键监听

## 安装依赖

```bash
pip install pyautogui pillow opencv-python numpy pytesseract keyboard
```

## 注意事项

1. 游戏模式下会自动关闭GAN以节省算力
2. 检测到死亡画面时会自动停止游戏
3. 失败记录会保存到经验模块，帮助AI学习
4. 正常操作记录会保存到记忆模块
5. 使用前请确保游戏窗口在前台显示
6. 不同游戏需要创建对应的配置文件来定义操作和死亡检测策略
7. 对于没有文字提示的游戏（如以撒的结合），建议启用scene_change和visual_cues检测方式