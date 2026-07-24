package com.humanaize.aizecompanion.service

import android.app.Notification
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.humanaize.aizecompanion.AizeApplication
import com.humanaize.aizecompanion.R
import com.humanaize.aizecompanion.compute.ComputeEngine
import com.humanaize.aizecompanion.network.IoTNetworkManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * 算力前台服务
 * 
 * 保持应用在后台运行，持续贡献算力。
 * 使用前台服务确保在长时间运行时不会被系统杀死。
 */
class ComputeService : Service() {
    
    companion object {
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "aize_compute_channel"
        
        const val ACTION_START = "com.humanaize.aizecompanion.START_COMPUTE"
        const val ACTION_STOP = "com.humanaize.aizecompanion.STOP_COMPUTE"
        
        fun start(context: Context) {
            val intent = Intent(context, ComputeService::class.java).apply {
                action = ACTION_START
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
        
        fun stop(context: Context) {
            val intent = Intent(context, ComputeService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }
    
    private lateinit var networkManager: IoTNetworkManager
    private lateinit var computeEngine: ComputeEngine
    
    override fun onCreate() {
        super.onCreate()
        
        val app = application as AizeApplication
        networkManager = app.iotNetworkManager
        computeEngine = ComputeEngine(networkManager)
        
        // 开始前台服务
        startForeground(NOTIFICATION_ID, createNotification())
        
        // 监听任务
        networkManager.onTaskReceived = { task ->
            computeEngine.processTask(task)
        }
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                // 确保连接
                val app = application as AizeApplication
                kotlinx.coroutines.CoroutineScope(
                    Dispatchers.IO
                ).launch {
                    app.settingsRepository.settingsFlow.first().let { settings ->
                        if (networkManager.connectionState.value != com.humanaize.aizecompanion.network.ConnectionState.CONNECTED) {
                            networkManager.connect(settings.serverAddress)
                        }
                    }
                }
            }
            ACTION_STOP -> {
                stopSelf()
            }
        }
        
        return START_STICKY
    }
    
    override fun onBind(intent: Intent?): IBinder? = null
    
    override fun onDestroy() {
        computeEngine.release()
        super.onDestroy()
    }
    
    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.notification_text_idle))
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }
}
