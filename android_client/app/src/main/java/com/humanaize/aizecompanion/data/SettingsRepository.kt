package com.humanaize.aizecompanion.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * 设置存储库
 * 
 * 使用 DataStore 持久化应用配置：
 * - 服务器地址
 * - 设备名称
 * - 算力贡献设置
 * - 贡献模式
 */
class SettingsRepository(private val context: Context) {
    
    companion object {
        private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(name = "aize_settings")
        
        val SERVER_ADDRESS = stringPreferencesKey("server_address")
        val DEVICE_NAME = stringPreferencesKey("device_name")
        val DEVICE_ID = stringPreferencesKey("device_id")
        val ENABLE_COMPUTE = booleanPreferencesKey("enable_compute")
        val MAX_TASKS = intPreferencesKey("max_concurrent_tasks")
        val CONTRIBUTION_MODE = stringPreferencesKey("contribution_mode")
        val ENABLE_REMOTE_SHELL = booleanPreferencesKey("enable_remote_shell")
        
        // 默认值
        const val DEFAULT_SERVER_ADDRESS = "ws://127.0.0.1:8765"
        const val DEFAULT_DEVICE_NAME = "Android Device"
        const val DEFAULT_MAX_TASKS = 1
        const val DEFAULT_CONTRIBUTION_MODE = "wifi"
        const val DEFAULT_ENABLE_REMOTE_SHELL = true
    }
    
    // 流式获取所有设置
    val settingsFlow: Flow<AppSettings> = context.settingsDataStore.data.map { preferences ->
        AppSettings(
            serverAddress = preferences[SERVER_ADDRESS] ?: DEFAULT_SERVER_ADDRESS,
            deviceName = preferences[DEVICE_NAME] ?: DEFAULT_DEVICE_NAME,
            deviceId = preferences[DEVICE_ID] ?: "",
            enableCompute = preferences[ENABLE_COMPUTE] ?: true,
            maxConcurrentTasks = preferences[MAX_TASKS] ?: DEFAULT_MAX_TASKS,
            contributionMode = preferences[CONTRIBUTION_MODE] ?: DEFAULT_CONTRIBUTION_MODE,
            enableRemoteShell = preferences[ENABLE_REMOTE_SHELL] ?: DEFAULT_ENABLE_REMOTE_SHELL
        )
    }
    
    suspend fun updateServerAddress(address: String) {
        context.settingsDataStore.edit { preferences ->
            preferences[SERVER_ADDRESS] = address
        }
    }
    
    suspend fun updateDeviceName(name: String) {
        context.settingsDataStore.edit { preferences ->
            preferences[DEVICE_NAME] = name
        }
    }
    
    suspend fun updateDeviceId(id: String) {
        context.settingsDataStore.edit { preferences ->
            preferences[DEVICE_ID] = id
        }
    }
    
    suspend fun updateEnableCompute(enabled: Boolean) {
        context.settingsDataStore.edit { preferences ->
            preferences[ENABLE_COMPUTE] = enabled
        }
    }
    
    suspend fun updateMaxConcurrentTasks(max: Int) {
        context.settingsDataStore.edit { preferences ->
            preferences[MAX_TASKS] = max.coerceIn(1, 4)
        }
    }
    
    suspend fun updateContributionMode(mode: String) {
        context.settingsDataStore.edit { preferences ->
            preferences[CONTRIBUTION_MODE] = mode
        }
    }
    
    suspend fun updateEnableRemoteShell(enabled: Boolean) {
        context.settingsDataStore.edit { preferences ->
            preferences[ENABLE_REMOTE_SHELL] = enabled
        }
    }
}

/**
 * 应用设置数据类
 */
data class AppSettings(
    val serverAddress: String = SettingsRepository.DEFAULT_SERVER_ADDRESS,
    val deviceName: String = SettingsRepository.DEFAULT_DEVICE_NAME,
    val deviceId: String = "",
    val enableCompute: Boolean = true,
    val maxConcurrentTasks: Int = SettingsRepository.DEFAULT_MAX_TASKS,
    val contributionMode: String = SettingsRepository.DEFAULT_CONTRIBUTION_MODE,
    val enableRemoteShell: Boolean = SettingsRepository.DEFAULT_ENABLE_REMOTE_SHELL
)
