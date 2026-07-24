package com.humanaize.aizecompanion

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.humanaize.aizecompanion.data.SettingsRepository
import com.humanaize.aizecompanion.network.IoTNetworkManager

/**
 * Aize Companion 应用程序主类
 * 
 * 负责初始化全局组件：
 * - 设置存储
 * - IoT 网络管理器
 * - 通知渠道
 */
class AizeApplication : Application() {
    
    lateinit var settingsRepository: SettingsRepository
        private set
    
    lateinit var iotNetworkManager: IoTNetworkManager
        private set
    
    override fun onCreate() {
        super.onCreate()
        instance = this
        
        // 初始化设置存储
        settingsRepository = SettingsRepository(this)
        
        // 初始化 IoT 网络管理器
        iotNetworkManager = IoTNetworkManager(settingsRepository)
        
        // 创建通知渠道
        createNotificationChannel()
    }
    
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.channel_compute_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.channel_compute_description)
                setShowBadge(false)
            }
            
            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }
    
    companion object {
        const val CHANNEL_ID = "aize_compute_channel"
        
        @Volatile
        private var instance: AizeApplication? = null
        
        fun getInstance(): AizeApplication = instance 
            ?: throw IllegalStateException("AizeApplication not created yet")
    }
}
