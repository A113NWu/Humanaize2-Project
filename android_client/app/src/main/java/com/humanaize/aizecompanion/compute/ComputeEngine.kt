package com.humanaize.aizecompanion.compute

import android.util.Log
import com.humanaize.aizecompanion.data.ComputeStats
import com.humanaize.aizecompanion.data.WsMessage
import com.humanaize.aizecompanion.network.IoTNetworkManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive

/**
 * 算力引擎
 * 
 * 处理从服务端接收到的计算任务：
 * - NLP 推理（通过 OnDeviceAI 或云端 API）
 * - 通用计算
 * - 数据处理
 * 
 * 为未来扩展本地 AI 推理做准备。
 */
class ComputeEngine(
    private val networkManager: IoTNetworkManager
) {
    companion object {
        private const val TAG = "ComputeEngine"
    }
    
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val json = Json { ignoreUnknownKeys = true }
    
    // 算力统计
    private val _stats = MutableStateFlow(ComputeStats())
    val stats: StateFlow<ComputeStats> = _stats.asStateFlow()
    
    // 当前正在处理的任务
    private var currentJob: Job? = null
    private val activeTasks = mutableMapOf<String, Job>()
    
    // 历史任务记录
    private val _completedTasks = MutableStateFlow<List<CompletedTask>>(emptyList())
    val completedTasks: StateFlow<List<CompletedTask>> = _completedTasks.asStateFlow()
    
    /**
     * 处理接收到的任务
     */
    fun processTask(task: WsMessage) {
        val taskId = task.task_id ?: return
        val taskType = task.action
        
        Log.i(TAG, "Processing task: $taskId, type: $taskType")
        
        // 更新统计信息
        _stats.value = _stats.value.copy(
            currentTaskId = taskId,
            isComputing = true
        )
        
        // 根据任务类型选择处理方式
        val job = scope.launch {
            try {
                val result = when (taskType) {
                    "assign_task" -> handleComputeTask(task)
                    "compute" -> handleComputeTask(task)
                    "nlp" -> handleNLPTask(task)
                    "data_processing" -> handleDataProcessing(task)
                    else -> handleGenericTask(task)
                }
                
                // 发送结果
                networkManager.sendTaskResult(
                    taskId = taskId,
                    success = true,
                    result = JsonPrimitive(result)
                )
                
                // 更新统计
                onTaskCompleted(taskId, true, result)
                
            } catch (e: Exception) {
                Log.e(TAG, "Task failed: ${e.message}")
                networkManager.sendTaskResult(
                    taskId = taskId,
                    success = false,
                    error = e.message
                )
                onTaskCompleted(taskId, false, null)
            }
        }
        
        activeTasks[taskId] = job
    }
    
    /**
     * 处理计算任务
     */
    private suspend fun handleComputeTask(task: WsMessage): String {
        // 模拟计算处理
        val payload = task.payload
        Log.d(TAG, "Computing with payload: $payload")
        
        // 简单的计算任务示例
        return when {
            payload != null -> {
                // 处理 JSON payload
                "Processed: ${payload}"
            }
            else -> "Completed"
        }
    }
    
    /**
     * 处理 NLP 任务
     */
    private suspend fun handleNLPTask(task: WsMessage): String {
        val message = task.message ?: return "No message to process"
        
        // 简单的 NLP 处理（本地处理）
        val processed = when {
            message.contains("摘要") || message.contains("summarize") -> {
                "摘要：${message.take(50)}..."
            }
            message.contains("翻译") || message.contains("translate") -> {
                "[翻译功能待集成]"
            }
            else -> {
                "[NLP 处理完成]"
            }
        }
        
        return processed
    }
    
    /**
     * 处理数据处理任务
     */
    private suspend fun handleDataProcessing(task: WsMessage): String {
        val payload = task.payload ?: return "No data"
        
        // 数据处理逻辑
        return "Data processed: ${payload}"
    }
    
    /**
     * 处理通用任务
     */
    private suspend fun handleGenericTask(task: WsMessage): String {
        return "[Task completed by Aize Companion]"
    }
    
    /**
     * 任务完成回调
     */
    private fun onTaskCompleted(taskId: String, success: Boolean, result: String?) {
        activeTasks.remove(taskId)
        
        val newStats = _stats.value
        val completedCount = newStats.totalTasksCompleted + 1
        val newComputeTime = newStats.totalComputeTimeMs + 1000 // 假设 1 秒
        
        _stats.value = newStats.copy(
            totalTasksCompleted = completedCount,
            totalComputeTimeMs = newComputeTime,
            currentTaskId = null,
            isComputing = false,
            tasksPerMinute = calculateTasksPerMinute(completedCount, newComputeTime)
        )
        
        // 添加到完成列表
        val completed = CompletedTask(
            taskId = taskId,
            success = success,
            result = result,
            completedAt = System.currentTimeMillis()
        )
        
        val currentList = _completedTasks.value.toMutableList()
        currentList.add(0, completed)
        _completedTasks.value = currentList.take(20) // 只保留最近 20 条
    }
    
    /**
     * 计算每分钟处理任务数
     */
    private fun calculateTasksPerMinute(totalTasks: Int, totalTimeMs: Long): Double {
        val minutes = totalTimeMs / 60000.0
        return if (minutes > 0) totalTasks / minutes else totalTasks.toDouble()
    }
    
    /**
     * 取消当前任务
     */
    fun cancelCurrentTask() {
        activeTasks.values.forEach { it.cancel() }
        activeTasks.clear()
        _stats.value = _stats.value.copy(
            currentTaskId = null,
            isComputing = false
        )
    }
    
    /**
     * 重置统计
     */
    fun resetStats() {
        _stats.value = ComputeStats()
        _completedTasks.value = emptyList()
    }
    
    /**
     * 释放资源
     */
    fun release() {
        cancelCurrentTask()
        scope.cancel()
    }
}

/**
 * 已完成任务记录
 */
data class CompletedTask(
    val taskId: String,
    val success: Boolean,
    val result: String?,
    val completedAt: Long
)
