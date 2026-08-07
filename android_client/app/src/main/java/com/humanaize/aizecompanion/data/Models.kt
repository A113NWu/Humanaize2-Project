package com.humanaize.aizecompanion.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * IoT 网络数据模型
 */

@Serializable
data class DeviceInfo(
    val device_id: String = "",
    val device_name: String = "",
    val device_type: String = "android_phone",
    val status: String = "offline",
    val capabilities: DeviceCapabilities = DeviceCapabilities(),
    val registered_at: Double = 0.0,
    val last_heartbeat: Double = 0.0,
    val total_tasks_completed: Int = 0,
    val total_compute_time: Double = 0.0
)

@Serializable
data class DeviceCapabilities(
    val can_compute: Boolean = true,
    val max_concurrent_tasks: Int = 1,
    val gpu_available: Boolean = false,
    val memory_gb: Double = 0.0,
    val cpu_cores: Int = 0,
    val supported_task_types: List<String> = emptyList(),
    val can_shell_exec: Boolean = false
)

@Serializable
data class ComputeTask(
    val task_id: String = "",
    val task_type: String = "general",
    val payload: JsonElement? = null,
    val assigned_device_id: String? = null,
    val status: String = "pending",
    val created_at: Double = 0.0,
    val started_at: Double = 0.0,
    val completed_at: Double = 0.0,
    val result: JsonElement? = null,
    val error_message: String = "",
    val retry_count: Int = 0,
    val max_retries: Int = 3
)

@Serializable
data class NetworkStats(
    val total_devices: Int = 0,
    val online_devices: Int = 0,
    val total_tasks: Int = 0,
    val completed_tasks: Int = 0,
    val failed_tasks: Int = 0,
    val is_running: Boolean = false,
    val host: String = "",
    val port: Int = 0
)

// WebSocket 消息结构
@Serializable
data class WsMessage(
    val action: String,
    val device_id: String? = null,
    val task_id: String? = null,
    val message: String? = null,
    val status: String? = null,
    val config: WsConfig? = null,
    val payload: JsonElement? = null,
    val result: JsonElement? = null,
    val error: String? = null,
    val conversation_id: String? = null,
    val content: String? = null,
    val timestamp: Double = 0.0,
    val timeout: Int? = null,
    val compute_time: Double? = null,
    val success: Boolean? = null,
    val device_name: String? = null,
    val device_type: String? = null,
    val can_compute: Boolean? = null,
    val max_concurrent_tasks: Int? = null,
    val cpu_cores: Int? = null,
    val memory_gb: Double? = null,
    val supported_task_types: List<String>? = null,
    // ===== Shell 命令相关字段 =====
    val shell_id: String? = null,         // Shell 执行请求 ID（用于匹配请求与响应）
    val command: String? = null,          // Shell 命令文本
    val work_dir: String? = null,         // 工作目录
    val env_vars: Map<String, String>? = null, // 环境变量
    val exit_code: Int? = null,           // 退出码
    val stdout: String? = null,           // 标准输出
    val stderr: String? = null,           // 标准错误
    val can_shell_exec: Boolean? = null   // 注册时上报能力：是否支持远程 Shell
)

@Serializable
data class WsConfig(
    val heartbeat_interval: Int = 30,
    val task_timeout: Int = 300,
    val server_version: String = "2.0.0"
)

// 聊天消息
@Serializable
data class ChatMessage(
    val id: String = "",
    val role: String = "user",  // "user" or "assistant"
    val content: String = "",
    val timestamp: Double = 0.0,
    val isStreaming: Boolean = false
)

// 算力统计
data class ComputeStats(
    val totalTasksCompleted: Int = 0,
    val totalComputeTimeMs: Long = 0L,
    val tasksPerMinute: Double = 0.0,
    val currentTaskId: String? = null,
    val currentTaskProgress: Float = 0f,
    val isComputing: Boolean = false
)

// 贡献模式枚举
enum class ContributionMode {
    IDLE_ONLY,  // 仅充电时
    WIFI_ONLY,  // 仅 WiFi 下
    ALWAYS      // 始终
}

fun String.toContributionMode(): ContributionMode = when (this) {
    "idle" -> ContributionMode.IDLE_ONLY
    "wifi" -> ContributionMode.WIFI_ONLY
    "always" -> ContributionMode.ALWAYS
    else -> ContributionMode.WIFI_ONLY
}

fun ContributionMode.toDisplayString(): String = when (this) {
    ContributionMode.IDLE_ONLY -> "idle"
    ContributionMode.WIFI_ONLY -> "wifi"
    ContributionMode.ALWAYS -> "always"
}
