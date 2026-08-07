package com.humanaize.aizecompanion.network

import android.util.Log
import com.humanaize.aizecompanion.data.SettingsRepository
import com.humanaize.aizecompanion.data.WsMessage
import com.humanaize.aizecompanion.shell.ShizukuShellExecutor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import okhttp3.*
import okio.ByteString
import java.util.concurrent.TimeUnit

/**
 * IoT 网络管理器
 * 
 * 负责与 Humanaize 2.0 服务端的 WebSocket 通信：
 * - 设备注册和认证
 * - 心跳维持
 * - 接收计算任务
 * - 发送任务结果
 * - 传递聊天消息
 */
class IoTNetworkManager(
    private val settingsRepository: SettingsRepository
) {
    companion object {
        private const val TAG = "IoTNetworkManager"
        private const val HEARTBEAT_INTERVAL = 30_000L
        private const val RECONNECT_DELAY = 5_000L
        private const val MAX_RECONNECT_ATTEMPTS = 10
    }
    
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val json = Json { ignoreUnknownKeys = true }
    
    private var webSocket: WebSocket? = null
    private var reconnectAttempts = 0
    private var heartbeatJob: kotlinx.coroutines.Job? = null
    private var isConnecting = false
    
    // 连接状态
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()
    
    // 设备 ID
    private val _deviceId = MutableStateFlow<String?>(null)
    val deviceId: StateFlow<String?> = _deviceId.asStateFlow()
    
    // 接收到的任务
    private val _pendingTask = MutableStateFlow<WsMessage?>(null)
    val pendingTask: StateFlow<WsMessage?> = _pendingTask.asStateFlow()
    
    // 聊天消息流
    private val _incomingChatMessage = MutableStateFlow<WsMessage?>(null)
    val incomingChatMessage: StateFlow<WsMessage?> = _incomingChatMessage.asStateFlow()
    
    // 流式聊天块
    private val _chatChunk = MutableStateFlow<ChatChunk?>(null)
    val chatChunk: StateFlow<ChatChunk?> = _chatChunk.asStateFlow()
    
    // 事件回调
    var onTaskReceived: ((WsMessage) -> Unit)? = null
    var onChatReceived: ((WsMessage) -> Unit)? = null
    var onConnectionChanged: ((ConnectionState) -> Unit)? = null
    var onShellExecReceived: ((WsMessage) -> Unit)? = null // 接收到 Shell 命令時的回調（用於 UI 提示）

    // 遠程 Shell 開關（由 SettingsRepository 同步）
    @Volatile
    private var enableRemoteShell: Boolean = true

    fun updateRemoteShellEnabled(enabled: Boolean) {
        enableRemoteShell = enabled
        Log.i(TAG, "Remote shell ${if (enabled) "enabled" else "disabled"}")
    }
    
    private val client = OkHttpClient.Builder()
        .retryOnConnectionFailure(true)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
    
    /**
     * 连接到服务器
     */
    suspend fun connect(serverAddress: String) {
        if (isConnecting || _connectionState.value == ConnectionState.CONNECTED) {
            return
        }
        
        isConnecting = true
        _connectionState.value = ConnectionState.CONNECTING
        onConnectionChanged?.invoke(ConnectionState.CONNECTING)
        
        try {
            val url = serverAddress.toWsUrl()
            val request = Request.Builder()
                .url(url)
                .build()
            
            Log.i(TAG, "Connecting to $url")
            
            webSocket = client.newWebSocket(request, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    Log.i(TAG, "WebSocket connected")
                    _connectionState.value = ConnectionState.CONNECTED
                    onConnectionChanged?.invoke(ConnectionState.CONNECTED)
                    reconnectAttempts = 0
                    
                    // 发送注册消息
                    scope.launch {
                        sendRegister()
                        startHeartbeat()
                    }
                }
                
                override fun onMessage(webSocket: WebSocket, text: String) {
                    handleMessage(text)
                }
                
                override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                    handleMessage(bytes.utf8())
                }
                
                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    webSocket.close(1000, null)
                }
                
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    Log.i(TAG, "WebSocket closed: code=$code, reason=$reason")
                    handleDisconnect()
                }
                
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    Log.e(TAG, "WebSocket failure: ${t.message}")
                    handleDisconnect()
                }
            })
        } catch (e: Exception) {
            Log.e(TAG, "Connection failed: ${e.message}")
            isConnecting = false
            _connectionState.value = ConnectionState.DISCONNECTED
            onConnectionChanged?.invoke(ConnectionState.DISCONNECTED)
            attemptReconnect(serverAddress)
        }
    }
    
    /**
     * 断开连接
     */
    fun disconnect() {
        heartbeatJob?.cancel()
        webSocket?.close(1000, "User disconnect")
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
        isConnecting = false
        reconnectAttempts = 0
    }
    
    /**
     * 发送注册消息
     */
    private suspend fun sendRegister() {
        val settings = settingsRepository.settingsFlow.first()

        val registerMsg = WsMessage(
            action = "register",
            device_name = settings.deviceName,
            device_type = "android_phone",
            can_compute = settings.enableCompute,
            max_concurrent_tasks = settings.maxConcurrentTasks,
            cpu_cores = Runtime.getRuntime().availableProcessors(),
            memory_gb = (Runtime.getRuntime().maxMemory() / (1024.0 * 1024.0 * 1024.0)),
            supported_task_types = listOf("general", "compute", "nlp"),
            // 遠程 Shell 能力：用戶開關 && Shizuku 權限可用
            can_shell_exec = (settings.enableRemoteShell && (ShizukuShellExecutor.checkPermission() == true))
        )

        sendMessage(registerMsg)
    }
    
    /**
     * 开始心跳
     */
    private fun startHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = scope.launch {
            while (_connectionState.value == ConnectionState.CONNECTED) {
                kotlinx.coroutines.delay(HEARTBEAT_INTERVAL)
                if (_connectionState.value == ConnectionState.CONNECTED) {
                    sendMessage(WsMessage(action = "heartbeat"))
                }
            }
        }
    }
    
    /**
     * 处理接收到的消息
     */
    private fun handleMessage(text: String) {
        try {
            val message = json.decodeFromString(WsMessage.serializer(), text)
            Log.d(TAG, "Received: ${message.action}")
            
            when (message.action) {
                "register_ack" -> {
                    message.device_id?.let { id ->
                        _deviceId.value = id
                        scope.launch {
                            settingsRepository.updateDeviceId(id)
                        }
                        Log.i(TAG, "Registered with device ID: $id")
                    }
                }
                
                "heartbeat_ack" -> {
                    // 心跳确认，无需特殊处理
                }
                
                "assign_task" -> {
                    _pendingTask.value = message
                    onTaskReceived?.invoke(message)
                }
                
                "chat_response" -> {
                    _incomingChatMessage.value = message
                    onChatReceived?.invoke(message)
                }
                
                "chat_stream_start" -> {
                    _chatChunk.value = ChatChunk.Start(message.conversation_id ?: "")
                }
                
                "chat_stream_chunk" -> {
                    _chatChunk.value = ChatChunk.Chunk(
                        message.conversation_id ?: "",
                        message.content ?: ""
                    )
                }
                
                "chat_stream_end" -> {
                    _chatChunk.value = ChatChunk.End(message.conversation_id ?: "")
                }
                
                "result_ack" -> {
                    // 结果确认
                    Log.d(TAG, "Result acknowledged for task: ${message.task_id}")
                }

                "shell_exec" -> {
                    // 服务端发来的 Shell 命令执行请求
                    scope.launch { handleShellExec(message) }
                    onShellExecReceived?.invoke(message)
                }
                
                else -> {
                    Log.d(TAG, "Unhandled action: ${message.action}")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse message: ${e.message}")
        }
    }
    
    /**
     * 发送消息到服务器
     */
    fun sendMessage(message: WsMessage) {
        val jsonStr = json.encodeToString(WsMessage.serializer(), message)
        scope.launch {
            val sent = webSocket?.send(jsonStr) ?: false
            if (!sent) {
                Log.w(TAG, "Failed to send message: ${message.action}")
            }
        }
    }
    
    /**
     * 发送任务结果
     */
    fun sendTaskResult(taskId: String, success: Boolean, result: kotlinx.serialization.json.JsonElement? = null, error: String? = null) {
        sendMessage(
            WsMessage(
                action = "task_result",
                task_id = taskId,
                success = success,
                result = result,
                error = error,
                compute_time = System.currentTimeMillis().toDouble()
            )
        )
    }
    
    /**
     * 发送聊天消息
     */
    fun sendChatMessage(message: String, conversationId: String? = null) {
        sendMessage(
            WsMessage(
                action = "chat_message",
                message = message,
                conversation_id = conversationId
            )
        )
    }
    
    /**
     * 发送流式聊天请求
     */
    fun sendChatStream(message: String, conversationId: String? = null) {
        sendMessage(
            WsMessage(
                action = "chat_stream",
                message = message,
                conversation_id = conversationId
            )
        )
    }

    /**
     * 處理遠程 Shell 命令執行請求
     */
    private suspend fun handleShellExec(message: WsMessage) {
        val shellId = message.shell_id
        val command = message.command
        val timeoutMs = (message.timeout ?: 30) * 1000L
        val workDir = message.work_dir
        val envVars = message.env_vars

        Log.i(TAG, "Shell exec requested: id=$shellId, cmd=${command?.take(120)}")

        if (command == null || command.isBlank()) {
            sendShellResult(
                shellId = shellId,
                success = false,
                exitCode = -1,
                stdout = "",
                stderr = "",
                error = "Empty command"
            )
            return
        }

        if (!enableRemoteShell) {
            sendShellResult(
                shellId = shellId,
                success = false,
                exitCode = -1,
                stdout = "",
                stderr = "",
                error = "Remote shell disabled in settings"
            )
            return
        }

        // 調用 Shizuku 執行命令
        val result = ShizukuShellExecutor.execute(command, timeoutMs, workDir, envVars)
        Log.i(TAG, "Shell finished: id=$shellId, exit=${result.exitCode}, time=${result.executionTimeMs}ms")

        sendShellResult(
            shellId = shellId,
            success = result.success,
            exitCode = result.exitCode,
            stdout = result.stdout,
            stderr = result.stderr,
            error = result.error,
            executionTimeMs = result.executionTimeMs
        )
    }

    /**
     * 發送 Shell 執行結果到服務端
     */
    private fun sendShellResult(
        shellId: String?,
        success: Boolean,
        exitCode: Int,
        stdout: String,
        stderr: String,
        error: String? = null,
        executionTimeMs: Long = 0L
    ) {
        sendMessage(
            WsMessage(
                action = "shell_result",
                shell_id = shellId,
                success = success,
                exit_code = exitCode,
                stdout = stdout,
                stderr = stderr,
                error = error,
                compute_time = executionTimeMs.toDouble()
            )
        )
    }
    
    /**
     * 处理断开连接
     */
    private fun handleDisconnect() {
        heartbeatJob?.cancel()
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
        isConnecting = false
        onConnectionChanged?.invoke(ConnectionState.DISCONNECTED)

        // 尝试重连（使用 first() 仅取一次当前值，避免 collect 无限挂起导致协程泄漏）
        scope.launch {
            val serverAddress = try {
                settingsRepository.settingsFlow.first().serverAddress
            } catch (t: Throwable) {
                Log.w(TAG, "handleDisconnect: failed to read settings: ${t.message}")
                return@launch
            }
            if (_connectionState.value == ConnectionState.DISCONNECTED) {
                attemptReconnect(serverAddress)
            }
        }
    }
    
    /**
     * 尝试重连
     */
    private fun attemptReconnect(serverAddress: String) {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            Log.w(TAG, "Max reconnect attempts reached")
            return
        }
        
        reconnectAttempts++
        val delay = RECONNECT_DELAY * reconnectAttempts
        
        Log.i(TAG, "Reconnecting in ${delay}ms (attempt $reconnectAttempts/$MAX_RECONNECT_ATTEMPTS)")
        
        scope.launch {
            kotlinx.coroutines.delay(delay)
            if (_connectionState.value == ConnectionState.DISCONNECTED) {
                connect(serverAddress)
            }
        }
    }
    
    /**
     * 释放资源
     */
    fun release() {
        disconnect()
        scope.cancel()
    }
    
    private fun String.toWsUrl(): String {
        return if (startsWith("wss://")) {
            this
        } else if (startsWith("ws://")) {
            this
        } else {
            "ws://$this"
        }
    }
}

/**
 * 连接状态枚举
 */
enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED
}

/**
 * 聊天数据块
 */
sealed class ChatChunk {
    data class Start(val conversationId: String) : ChatChunk()
    data class Chunk(val conversationId: String, val content: String) : ChatChunk()
    data class End(val conversationId: String) : ChatChunk()
}
