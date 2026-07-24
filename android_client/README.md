# Aize Companion - Humanaize 2.0 安卓客户端

允许用户将 Android 设备接入 Humanaize 2.0 算力网络，贡献闲置算力并与 Aize 进行对话。

## 功能特性

- **🔗 分布式算力贡献**：将手机闲置算力用于分布式任务处理
- **💬 与 Aize 对话**：直接在手机上与 Aize 进行智能对话
- **📊 实时统计**：查看算力贡献统计和任务历史
- **🔄 自动重连**：网络断开时自动重试连接
- **🔋 智能模式**：支持 WiFi 下/充电时/始终三种贡献模式
- **📱 现代 UI**：基于 Jetpack Compose 的 Material Design 3 界面

## 技术栈

- **Kotlin 1.9.20**
- **Jetpack Compose** - 现代声明式 UI
- **OkHttp** - WebSocket 通信
- **Kotlinx Serialization** - JSON 序列化
- **DataStore** - 持久化存储
- **Coroutines** - 异步处理

## 架构

```
┌─────────────────┐     WebSocket      ┌─────────────────────┐
│  Aize Companion  │ ◄────────────────► │  Humanaize 2.0 服務端 │
│  (Android 手機)   │   ws://ip:8765    │  (Python 主程序)      │
└─────────────────┘                     └─────────────────────┘
         │                                       │
         ▼                                       ▼
  ┌─────────────┐                        ┌─────────────────┐
  │ ComputeEngine │                        │ IoTComputeManager │
  │ 本地算力處理   │                        │  (獨立於 HSN)      │
  └─────────────┘                        └─────────────────┘
                                                   │
                                                   │ 獨立
                                                   ▼
                                          ┌─────────────────┐
                                          │ HSN (AI 協作)    │
                                          │ AI-to-AI 溝通    │
                                          └─────────────────┘
```

**重要說明**：IoT 算力網絡與 HSN 是兩個完全獨立的系統：
- **IoT 算力網絡**：管理分佈式設備（手機、平板等）的算力貢獻
- **HSN**：管理 AI 與 AI 之間的溝通協作

## 快速开始

### 1. 环境要求

- Android Studio Hedgehog (2023.1.1) 或更新版本
- JDK 17
- Android SDK 34
- 最低支持 API 24 (Android 7.0)

### 2. 构建步骤

```bash
cd android_client

# 使用 Gradle Wrapper 构建
./gradlew assembleDebug

# 或使用 Android Studio
# File → Open → 选择 android_client 目录
```

### 3. 安装到设备

```bash
# 连接 Android 设备后
adb install app/build/outputs/apk/debug/app-debug.apk
```

## 使用流程

### 启动服务端

首先在电脑上启动 Humanaize 2.0 的 IoT 算力网络服务（与 HSN 独立）：

```bash
./humanaize2.sh boot -m iot
# 或
humanaize2.bat boot -m iot
# 或指定地址和端口
./humanaize2.sh boot -m iot --host 0.0.0.0 --port 8765
```

服务启动后，IoT 算力网络会在 `ws://0.0.0.0:8765` 上监听。

### IoT 算力網絡與 HSN 的區別

| 功能 | IoT 算力網絡 | HSN |
|------|-------------|-----|
| **目的** | 利用分佈式設備的 CPU/GPU 算力 | AI 與 AI 之間的溝通協作 |
| **連接對象** | 手機、平板、其他計算機 | 其他 Aize 實例 |
| **主要功能** | 算力貢獻、任務分發 | AI 對話、問題協作解決 |
| **啟動方式** | `boot -m iot` | `boot -m solve --hsn` |

### 连接手机

1. 确保手机和电脑在同一局域网
2. 在手机上打开 Aize Companion
3. 在设置页面填入电脑 IP 和端口：`ws://<电脑IP>:8765`
4. 点击"保存"后自动连接

### 开始贡献算力

1. 进入"算力"页面
2. 打开"算力贡献"开关
3. 选择贡献模式（推荐"仅 WiFi 下"）
4. 点击"启动算力"开始贡献

### 与 Aize 对话

1. 进入"对话"页面
2. 在输入框输入消息
3. 点击发送按钮
4. Aize 会流式响应你的消息

## WebSocket 协议

### 客户端 → 服务端

| Action | 描述 | 关键字段 |
|--------|------|---------|
| `register` | 设备注册 | device_name, device_type, capabilities |
| `heartbeat` | 心跳保活 | - |
| `task_result` | 任务结果 | task_id, success, result |
| `chat_message` | 聊天消息 | message, conversation_id |
| `chat_stream` | 流式聊天 | message, conversation_id |
| `disconnect` | 断开连接 | - |

### 服务端 → 客户端

| Action | 描述 | 关键字段 |
|--------|------|---------|
| `register_ack` | 注册确认 | device_id, config |
| `heartbeat_ack` | 心跳确认 | device_id |
| `assign_task` | 分配任务 | task_id, task_type, payload |
| `chat_response` | 聊天回复 | message, conversation_id |
| `chat_stream_start` | 流式开始 | conversation_id |
| `chat_stream_chunk` | 流式块 | content, conversation_id |
| `chat_stream_end` | 流式结束 | conversation_id |
| `result_ack` | 结果确认 | task_id |

## 项目结构

```
android_client/
├── app/
│   ├── src/main/
│   │   ├── java/com/humanaize/aizecompanion/
│   │   │   ├── AizeApplication.kt      # Application 主类
│   │   │   ├── data/
│   │   │   │   ├── Models.kt            # 数据模型
│   │   │   │   └── SettingsRepository.kt # 设置存储
│   │   │   ├── network/
│   │   │   │   └── IoTNetworkManager.kt  # WebSocket 管理
│   │   │   ├── compute/
│   │   │   │   └── ComputeEngine.kt     # 算力引擎
│   │   │   ├── service/
│   │   │   │   ├── ComputeService.kt    # 前台服务
│   │   │   │   └── DiscoveryService.kt  # 设备发现
│   │   │   └── ui/
│   │   │       ├── MainActivity.kt      # 主 Activity
│   │   │       ├── theme/Theme.kt        # 主题配置
│   │   │       ├── viewmodel/
│   │   │       │   └── MainViewModel.kt  # 主 ViewModel
│   │   │       └── screens/
│   │   │           ├── HomeScreen.kt    # 首页
│   │   │           ├── ComputeScreen.kt # 算力页
│   │   │           ├── ChatScreen.kt    # 聊天页
│   │   │           └── SettingsScreen.kt # 设置页
│   │   └── res/
│   └── build.gradle.kts
├── build.gradle.kts
├── settings.gradle.kts
└── gradle.properties
```

## 服务端集成

在 Humanaize 2.0 服务端，IoT 算力管理器是完全独立的模块，与 HSN 互不影响：

```python
from tools.iot_compute_manager import IoTComputeManager

# 启动 IoT 算力网络
manager = IoTComputeManager()
manager.initialize()
manager.start()

# 提交计算任务
task_id = manager.submit_task('compute', {'data': '...'})

# 获取结果
result = manager.wait_for_result(task_id)

# 与设备对话
manager.send_chat('device-id', '你好 Aize')

# 获取统计
stats = manager.get_stats()
```

或者直接使用命令行：
```bash
./humanaize2.sh boot -m iot           # 启动 IoT 网络
./humanaize2.sh boot -m solve --hsn   # 启动 HSN（AI 协作）
```

## 常见问题

### Q: 连接不上服务器？
A: 确保手机和电脑在同一 WiFi 网络，检查防火墙是否允许 8765 端口入站连接。

### Q: 如何在手机上访问本地 IP？
A: 在 Windows 上运行 `ipconfig` 查看局域网 IP，在 Linux/Mac 上运行 `ifconfig` 或 `ip addr`。

### Q: 算力贡献会耗电吗？
A: 会的，建议在充电时或 WiFi 下使用。可以在设置中调整贡献模式。

### Q: 支持哪些任务类型？
A: 目前支持 `general`、`compute`、`nlp` 和 `data_processing` 类型。更多类型将在后续版本添加。

## 版本历史

- **v1.0.0** - 初始版本，支持设备连接、算力贡献和 Aize 对话

## 许可证

本项目是 Humanaize 2.0 Agent 的一部分，遵循项目许可证。
