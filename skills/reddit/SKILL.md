---
name: reddit
description: Reddit浏览技能，让Aize可以浏览和搜索Reddit论坛内容
metadata:
  category: social
  risk_level: low
  requires_approval: false
  version: 1.0.0
---

# Reddit浏览技能

## 功能描述

让Aize可以浏览和搜索Reddit论坛内容，包括热门帖子、子版块、评论等。

## 前置条件

### 1. 需要创建Reddit开发者应用

要使用Reddit API，你需要在Reddit创建一个开发者应用并获取API凭证。

### 2. 需要安装praw库

```bash
pip install praw --break-system-packages
```

## 详细配置步骤

### 步骤1：创建Reddit账号（如果还没有）

1. 访问 https://www.reddit.com
2. 点击右上角的"Sign Up"注册账号
3. 完成邮箱验证

### 步骤2：创建Reddit开发者应用

1. 访问 https://www.reddit.com/prefs/apps
2. 点击页面底部的"Create App"或"Create Another App"按钮
3. 填写应用信息：

| 字段 | 值 | 说明 |
|------|-----|------|
| Name | Humanaize | 应用名称，可以自定义 |
| Type | Script | 选择"Script"类型 |
| Description | Humanaize Reddit browsing skill | 应用描述 |
| About URL | 留空 | 可选 |
| Redirect URI | http://localhost:8080 | 必须填写，任意有效URL均可 |

4. 点击"Create App"按钮

### 步骤3：获取API凭证

创建成功后，你会看到应用信息页面：

- **client_id**：位于应用名称下方，形如 `xxxxxxxxx`（一串随机字符）
- **client_secret**：显示为"secret"字段的值

### 步骤4：配置Humanaize Reddit技能

#### 方法一：通过技能调用配置

```json
{"skill": "reddit", "input": {"action": "configure", "params": {"client_id": "你的client_id", "client_secret": "你的client_secret", "user_agent": "Humanaize/1.0", "mock_mode": false}}}
```

#### 方法二：直接编辑配置文件

编辑 `/home/allenwu/桌面/Humanaize_2_1/skills/reddit/config.json`：

```json
{
  "client_id": "你的client_id",
  "client_secret": "你的client_secret",
  "user_agent": "Humanaize/1.0",
  "mock_mode": false
}
```

### 步骤5：验证配置

```json
{"skill": "reddit", "input": {"action": "status"}}
```

如果配置成功，会返回：

```json
{
  "success": true,
  "praw_available": true,
  "configured": true,
  "connected": true,
  "mock_mode": false,
  "user_agent": "Humanaize/1.0"
}
```

## 使用方法

### 获取热门帖子

```json
{"skill": "reddit", "input": {"action": "hot", "params": {"limit": 10}}}
```

### 获取新帖子

```json
{"skill": "reddit", "input": {"action": "new", "params": {"limit": 10}}}
```

### 获取置顶帖子

```json
{"skill": "reddit", "input": {"action": "top", "params": {"limit": 10, "time_filter": "day"}}}
```

**time_filter可选值**：
- `hour` - 过去1小时
- `day` - 过去24小时（默认）
- `week` - 过去一周
- `month` - 过去一个月
- `year` - 过去一年
- `all` - 所有时间

### 搜索帖子

```json
{"skill": "reddit", "input": {"action": "search", "params": {"query": "AI", "limit": 10}}}
```

### 浏览子版块

```json
{"skill": "reddit", "input": {"action": "subreddit", "params": {"name": "technology", "sort": "hot", "limit": 10}}}
```

**sort可选值**：
- `hot` - 热门（默认）
- `new` - 最新
- `top` - 置顶

### 获取帖子评论

```json
{"skill": "reddit", "input": {"action": "comments", "params": {"url": "https://reddit.com/r/technology/comments/xxx", "limit": 10}}}
```

### 获取状态

```json
{"skill": "reddit", "input": {"action": "status"}}
```

## 常用子版块推荐

| 子版块 | 描述 |
|--------|------|
| r/technology | 科技新闻 |
| r/programming | 编程讨论 |
| r/Python | Python编程 |
| r/learnprogramming | 学习编程 |
| r/worldnews | 世界新闻 |
| r/science | 科学资讯 |
| r/space | 太空探索 |
| r/gaming | 游戏讨论 |
| r/movies | 电影讨论 |
| r/AskReddit | 问答社区 |

## 配置参数说明

| 参数 | 类型 | 描述 | 默认值 |
|------|------|------|--------|
| client_id | string | Reddit应用client_id | 无 |
| client_secret | string | Reddit应用client_secret | 无 |
| user_agent | string | 用户代理标识 | Humanaize/1.0 |
| mock_mode | bool | 是否启用模拟模式（不连接真实Reddit） | true |

## 返回格式

```json
{
  "success": true,
  "action": "hot",
  "results": [
    {
      "title": "帖子标题",
      "url": "帖子链接",
      "subreddit": "子版块",
      "score": 1000,
      "num_comments": 100,
      "author": "作者",
      "created": "时间"
    }
  ]
}
```

## 常见问题

### Q1：配置后无法连接怎么办？
- 确认client_id和client_secret正确
- 确认网络可以访问Reddit（可能需要使用代理）
- 确认user_agent格式正确（建议格式：`应用名/版本号`）
- 检查Reddit账号是否已验证邮箱

### Q2：请求被限制怎么办？
- Reddit API有请求频率限制（每分钟60次）
- 如果遇到限制，等待一段时间后重试
- 避免在短时间内发送大量请求

### Q3：如何访问被墙的Reddit？

如果在中国大陆，Reddit可能无法直接访问。可以使用以下方法：

#### 方法一：使用代理

设置环境变量：

```bash
export http_proxy=http://proxy:port
export https_proxy=http://proxy:port
```

或者在技能配置中添加代理设置（需要修改代码）。

#### 方法二：使用VPN

连接VPN后再使用Reddit技能。

### Q4：可以发布帖子或评论吗？

当前技能仅支持只读操作（浏览、搜索），不支持发布帖子或评论。如需写操作，需要修改代码并在Reddit应用配置中添加相应权限。

## 注意事项

1. 需要确保网络可以访问Reddit
2. 需要正确配置API凭证
3. Reddit有请求频率限制，请合理使用
4. 遵守Reddit的使用条款和API使用规范
5. 建议使用模拟模式测试功能后再启用真实模式