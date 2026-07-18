---
name: qq-chat
description: QQ聊天技能，让Aize可以通过QQ与用户聊天
metadata:
  category: social
  risk_level: medium
  requires_approval: false
  version: 1.0.0
---

# QQ聊天技能

## 功能描述

让Aize可以通过QQ与用户进行聊天，支持发送和接收私聊消息、群消息。

## 支持的后端协议

| 协议 | 说明 | 默认端口 | 推荐度 |
|------|------|----------|--------|
| astrbot | Astrbot机器人框架API | 6185 | ⭐⭐⭐ 推荐 |
| milky | Lagrange.Milky协议 | 3000 | ⭐⭐ |
| onebot | OneBot标准协议 | 8080 | ⭐⭐⭐ |

## Astrbot配置指南

### 第一步：安装Astrbot

#### 方式一：Docker部署（推荐）

```bash
# 安装Docker（需要sudo权限）
curl -fsSL https://get.docker.com | sh

# 创建目录并下载配置
mkdir -p ~/astrbot && cd ~/astrbot
wget https://raw.githubusercontent.com/NapNeko/NapCat-Docker/main/compose/astrbot.yml

# 启动容器
sudo docker compose -f astrbot.yml up -d
```

#### 方式二：手动部署

```bash
# 安装依赖
sudo apt update && sudo apt install -y python3-full python3-dev python3-venv git

# 创建目录
mkdir -p ~/astrbot && cd ~/astrbot

# 下载源码（需要能访问GitHub或使用代理）
git clone https://github.com/AstrBotDevs/AstrBot.git .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动
python3 main.py
```

### 第二步：配置NapCat

1. 访问NapCat管理后台：`http://localhost:6099`
2. 使用QQ扫码登录
3. 确认WebSocket配置指向Astrbot

### 第三步：配置Astrbot

1. 访问Astrbot管理后台：`http://localhost:6185`
2. 默认用户名密码：`astrbot` / `astrbot`
3. 进入「消息平台」→「新增适配器」→「接入QQ个人号（aiocqhttp）」
4. 保持默认配置，勾选启用

### 第四步：配置Humanaize QQ技能

#### 方法一：通过技能调用配置

```json
{"skill": "qq-chat", "input": {"action": "configure", "params": {"host": "127.0.0.1", "port": 6185, "qq": 123456789, "enabled": true, "mock_mode": false, "protocol": "astrbot", "token": ""}}}
```

#### 方法二：直接编辑配置文件

```bash
cat > /home/allenwu/桌面/Humanaize_2_1/skills/qq-chat/config.json << 'EOF'
{
  "host": "127.0.0.1",
  "port": 6185,
  "qq": 123456789,
  "enabled": true,
  "mock_mode": false,
  "protocol": "astrbot",
  "token": ""
}
EOF
```

### 第五步：验证配置

```json
{"skill": "qq-chat", "input": {"action": "status"}}
```

预期输出：

```json
{
  "success": true,
  "enabled": true,
  "mock_mode": false,
  "connected": true,
  "qq": 123456789,
  "host": "127.0.0.1",
  "port": 6185,
  "protocol": "astrbot",
  "message_count": 0
}
```

## 使用方法

### 发送私聊消息

```json
{"skill": "qq-chat", "input": {"action": "send", "params": {"to": 987654321, "message": "你好！我是Aize"}}}
```

### 发送群消息

```json
{"skill": "qq-chat", "input": {"action": "send_group", "params": {"group_id": 123456789, "message": "大家好！"}}}
```

### 接收消息

```json
{"skill": "qq-chat", "input": {"action": "receive", "params": {"limit": 10}}}
```

### 获取状态

```json
{"skill": "qq-chat", "input": {"action": "status"}}
```

## 配置参数说明

| 参数 | 类型 | 描述 | 默认值 |
|------|------|------|--------|
| host | string | QQ机器人后端地址 | 127.0.0.1 |
| port | int | QQ机器人后端端口 | 6185 |
| qq | int | QQ账号 | 无 |
| enabled | bool | 是否启用 | false |
| mock_mode | bool | 是否启用模拟模式（不连接真实QQ） | true |
| protocol | string | 协议类型（astrbot/milky/onebot） | astrbot |
| token | string | API访问令牌（如需要） | 空 |

## 常见问题

### Q1：Astrbot安装失败怎么办？
- 确认网络可以访问GitHub（国内用户可能需要代理）
- 尝试使用Docker方式部署
- 检查Python版本是否为3.12+

### Q2：QQ无法登录怎么办？
- 使用QQ小号作为机器人账号
- 确保QQ已完成设备锁验证
- 检查NapCat日志获取详细错误信息

### Q3：消息发送失败怎么办？
- 确认Astrbot和NapCat服务都在运行
- 确认QQ账号已成功登录
- 检查网络连接和端口配置

### Q4：如何设置开机自启？

Docker方式自动支持重启，手动部署可以使用systemd：

```bash
sudo bash -c 'cat > /etc/systemd/system/astrbot.service << "EOF"
[Unit]
Description=AstrBot QQ Bot
After=network.target

[Service]
Type=simple
User=allenwu
WorkingDirectory=/home/allenwu/astrbot
ExecStart=/home/allenwu/astrbot/venv/bin/python /home/allenwu/astrbot/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable astrbot
sudo systemctl start astrbot
```

## 注意事项

1. 需要确保Astrbot和NapCat服务正在运行
2. 需要确保网络连接正常
3. 请勿在公共场合泄露QQ账号信息
4. QQ机器人需要遵守QQ官方服务协议
5. 建议使用小号作为机器人账号