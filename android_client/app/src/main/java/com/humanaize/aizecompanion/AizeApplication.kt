package com.humanaize.aizecompanion

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.humanaize.aizecompanion.data.SettingsRepository
import com.humanaize.aizecompanion.network.AizeApiClient
import com.humanaize.aizecompanion.service.PhoneCommandPoller
import com.humanaize.aizecompanion.shell.ShizukuShellExecutor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/**
 * Aize Companion 應用主類
 *
 * 初始化：設定存儲、API 客戶端、手機命令輪詢器。
 * 輪詢器跟隨設定自動啟停：開啟遠程 shell 且已配置服務器時運行。
 */
class AizeApplication : Application() {

    lateinit var settingsRepository: SettingsRepository
        private set

    lateinit var apiClient: AizeApiClient
        private set

    lateinit var commandPoller: PhoneCommandPoller
        private set

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onCreate() {
        super.onCreate()
        instance = this

        // 儘早註冊 Shizuku sticky binder 監聽，避免 checkSelfPermission 誤報未授權
        ShizukuShellExecutor.init(this)
        ShizukuShellExecutor.ensureInit()
        // 服務已在跑但本進程沒收到 binder 時，主動補一次
        ShizukuShellExecutor.requestBinder(force = true)

        settingsRepository = SettingsRepository(this)
        apiClient = AizeApiClient("", "")
        commandPoller = PhoneCommandPoller(apiClient)

        // 跟隨設定驅動 API 配置與輪詢器啟停
        appScope.launch {
            settingsRepository.settingsFlow.collect { s ->
                apiClient.updateConfig(s.baseUrl, s.sessionToken)
                commandPoller.deviceName = s.deviceName
                if (s.enableRemoteShell && s.baseUrl.isNotEmpty()) {
                    commandPoller.start()
                } else {
                    commandPoller.stop()
                }
            }
        }

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
            getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
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
