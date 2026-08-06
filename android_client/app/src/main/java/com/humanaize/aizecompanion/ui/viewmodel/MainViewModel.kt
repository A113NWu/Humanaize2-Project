package com.humanaize.aizecompanion.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.humanaize.aizecompanion.AizeApplication
import com.humanaize.aizecompanion.compute.ComputeEngine
import com.humanaize.aizecompanion.data.AppSettings
import com.humanaize.aizecompanion.data.ChatMessage
import com.humanaize.aizecompanion.data.ComputeStats
import com.humanaize.aizecompanion.data.WsMessage
import com.humanaize.aizecompanion.network.ChatChunk
import com.humanaize.aizecompanion.network.ConnectionState
import com.humanaize.aizecompanion.network.IoTNetworkManager
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive

/**
 * 主 ViewModel
 * 
 * 管理应用所有 UI 状态和业务逻辑：
 * - 网络连接状态
 * - 算力统计
 * - 聊天消息
 * - 设置
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MainViewModel(application: Application) : AndroidViewModel(application) {
    
    private val app = application as AizeApplication
    private val networkManager = app.iotNetworkManager
    private val computeEngine = ComputeEngine(networkManager)
    private val settingsRepo = app.settingsRepository
    
    // 连接状态
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<String> = _connectionState.map { it.name.lowercase() }
        .stateIn(viewModelScope, SharingStarted.Eagerly, "disconnected")
    
    // 设置
    private val _settings = MutableStateFlow(AppSettings())
    val settings: StateFlow<AppSettings> = _settings.asStateFlow()
    
    // 算力统计
    val computeStats: StateFlow<ComputeStats> = computeEngine.stats
    val completedTasks = computeEngine.completedTasks
    
    // 聊天消息列表
    private val _chatMessages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val chatMessages: StateFlow<List<ChatMessage>> = _chatMessages.asStateFlow()
    
    // 聊天加载状态
    private val _chatLoading = MutableStateFlow(false)
    val chatLoading: StateFlow<Boolean> = _chatLoading.asStateFlow()
    
    // 流式聊天临时消息
    private val _streamingMessage = MutableStateFlow<ChatMessage?>(null)
    val streamingMessage: StateFlow<ChatMessage?> = _streamingMessage.asStateFlow()
    
    init {
        // 监听连接状态
        viewModelScope.launch {
            networkManager.connectionState.collect { state ->
                _connectionState.value = state
            }
        }
        
        // 监听设置变化
        viewModelScope.launch {
            settingsRepo.settingsFlow.collect { settings ->
                _settings.value = settings
                // 同步遠程 Shell 開關到網絡管理器
                networkManager.updateRemoteShellEnabled(settings.enableRemoteShell)
            }
        }
        
        // 监听任务接收
        networkManager.onTaskReceived = { task ->
            viewModelScope.launch {
                computeEngine.processTask(task)
            }
        }
        
        // 监听聊天消息
        viewModelScope.launch {
            networkManager.incomingChatMessage.collect { message ->
                message?.let { msg ->
                    handleIncomingChat(msg)
                }
            }
        }
        
        // 监听聊天流
        viewModelScope.launch {
            networkManager.chatChunk.collect { chunk ->
                chunk?.let { handleChatChunk(it) }
            }
        }
        
        // 自动连接（如果有保存的服务器地址）
        viewModelScope.launch {
            settingsRepo.settingsFlow.first().let { settings ->
                if (settings.serverAddress.isNotEmpty()) {
                    connectToServer(settings.serverAddress)
                }
            }
        }
    }
    
    /**
     * 连接到服务器
     */
    fun connectToServer(address: String) {
        viewModelScope.launch {
            networkManager.connect(address)
        }
    }
    
    /**
     * 断开连接
     */
    fun disconnect() {
        networkManager.disconnect()
    }
    
    /**
     * 发送聊天消息
     */
    fun sendChatMessage(message: String) {
        if (message.isBlank()) return
        
        val userMessage = ChatMessage(
            id = generateId(),
            role = "user",
            content = message,
            timestamp = System.currentTimeMillis().toDouble()
        )
        
        _chatMessages.value = _chatMessages.value + userMessage
        _chatLoading.value = true
        
        // 发送到服务器（使用流式）
        networkManager.sendChatStream(message)
    }
    
    /**
     * 处理接收到的聊天消息
     */
    private fun handleIncomingChat(message: WsMessage) {
        val chatMessage = ChatMessage(
            id = generateId(),
            role = "assistant",
            content = message.message ?: "",
            timestamp = System.currentTimeMillis().toDouble()
        )
        
        _chatMessages.value = _chatMessages.value + chatMessage
        _chatLoading.value = false
    }
    
    /**
     * 处理流式聊天块
     */
    private fun handleChatChunk(chunk: ChatChunk) {
        when (chunk) {
            is ChatChunk.Start -> {
                // 开始新的流式响应
                _streamingMessage.value = ChatMessage(
                    id = generateId(),
                    role = "assistant",
                    content = "",
                    timestamp = System.currentTimeMillis().toDouble(),
                    isStreaming = true
                )
                _chatLoading.value = true
            }
            is ChatChunk.Chunk -> {
                // 追加内容
                val current = _streamingMessage.value
                if (current != null) {
                    _streamingMessage.value = current.copy(
                        content = current.content + chunk.content
                    )
                }
            }
            is ChatChunk.End -> {
                // 结束流式响应
                val finalMessage = _streamingMessage.value
                if (finalMessage != null && finalMessage.content.isNotBlank()) {
                    _chatMessages.value = _chatMessages.value + finalMessage.copy(isStreaming = false)
                }
                _streamingMessage.value = null
                _chatLoading.value = false
            }
        }
    }
    
    /**
     * 更新服务器地址
     */
    fun updateServerAddress(address: String) {
        viewModelScope.launch {
            settingsRepo.updateServerAddress(address)
            // 如果已连接，重连
            if (_connectionState.value == ConnectionState.CONNECTED) {
                networkManager.disconnect()
                connectToServer(address)
            }
        }
    }
    
    /**
     * 更新设备名称
     */
    fun updateDeviceName(name: String) {
        viewModelScope.launch {
            settingsRepo.updateDeviceName(name)
        }
    }
    
    /**
     * 更新算力设置
     */
    fun updateComputeEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepo.updateEnableCompute(enabled)
        }
    }
    
    fun updateMaxConcurrentTasks(max: Int) {
        viewModelScope.launch {
            settingsRepo.updateMaxConcurrentTasks(max)
        }
    }
    
    fun updateContributionMode(mode: String) {
        viewModelScope.launch {
            settingsRepo.updateContributionMode(mode)
        }
    }

    /**
     * 更新遠程 Shell 開關
     */
    fun updateRemoteShellEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepo.updateEnableRemoteShell(enabled)
            networkManager.updateRemoteShellEnabled(enabled)
        }
    }

    /**
     * 查詢 Shizuku 服務狀態：null=未安裝/未啟動；true=已授權；false=未授權
     */
    fun getShizukuStatus(): Boolean? {
        return com.humanaize.aizecompanion.shell.ShizukuShellExecutor.checkPermission()
    }

    /**
     * 請求 Shizuku 權限（需在 Activity 上下文調用，Shizuku 會彈窗）
     */
    suspend fun requestShizukuPermission(): Boolean {
        return com.humanaize.aizecompanion.shell.ShizukuShellExecutor.requestPermission()
    }
    
    /**
     * 重置算力统计
     */
    fun resetComputeStats() {
        computeEngine.resetStats()
    }
    
    /**
     * 清除聊天记录
     */
    fun clearChatHistory() {
        _chatMessages.value = emptyList()
        _streamingMessage.value = null
    }
    
    private fun generateId(): String {
        return System.currentTimeMillis().toString() + 
               (0..999).random().toString().padStart(3, '0')
    }
    
    override fun onCleared() {
        super.onCleared()
        computeEngine.release()
    }
}
