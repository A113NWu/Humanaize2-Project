package com.humanaize.aizecompanion.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * 设置存储库
 *
 * DataStore 持久化：
 * - 服务器地址（PC 端 Humanaize2，如 192.168.1.10:8082）
 * - 登录账号/密码与会话 token（Bearer）
 * - 设备名（手机在 PC 端的显示名）
 * - 远程 shell 开关（允许 Aize 下發命令到本机执行）
 */
class SettingsRepository(private val context: Context) {

    companion object {
        private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(name = "aize_settings")

        val SERVER_ADDRESS = stringPreferencesKey("server_address")
        val USERNAME = stringPreferencesKey("username")
        val PASSWORD = stringPreferencesKey("password")
        val SESSION_TOKEN = stringPreferencesKey("session_token")
        val DEVICE_NAME = stringPreferencesKey("device_name")
        val ENABLE_REMOTE_SHELL = booleanPreferencesKey("enable_remote_shell")
        val ENABLE_LIVE2D_POPUP = booleanPreferencesKey("enable_live2d_popup")

        const val DEFAULT_SERVER_ADDRESS = ""
        const val DEFAULT_DEVICE_NAME = "Android Phone"
        const val DEFAULT_ENABLE_REMOTE_SHELL = false
    }

    val settingsFlow: Flow<AppSettings> = context.settingsDataStore.data.map { p ->
        AppSettings(
            serverAddress = p[SERVER_ADDRESS] ?: DEFAULT_SERVER_ADDRESS,
            username = p[USERNAME] ?: "",
            password = p[PASSWORD] ?: "",
            sessionToken = p[SESSION_TOKEN] ?: "",
            deviceName = p[DEVICE_NAME] ?: DEFAULT_DEVICE_NAME,
            enableRemoteShell = p[ENABLE_REMOTE_SHELL] ?: DEFAULT_ENABLE_REMOTE_SHELL
        )
    }

    suspend fun updateServerAddress(address: String) {
        context.settingsDataStore.edit { it[SERVER_ADDRESS] = address.trim() }
    }

    suspend fun updateCredentials(username: String, password: String) {
        context.settingsDataStore.edit {
            it[USERNAME] = username.trim()
            it[PASSWORD] = password
        }
    }

    suspend fun updateSessionToken(token: String) {
        context.settingsDataStore.edit { it[SESSION_TOKEN] = token }
    }

    suspend fun updateDeviceName(name: String) {
        context.settingsDataStore.edit { it[DEVICE_NAME] = name.trim() }
    }

    suspend fun updateEnableRemoteShell(enabled: Boolean) {
        context.settingsDataStore.edit { it[ENABLE_REMOTE_SHELL] = enabled }
    }
}

data class AppSettings(
    val serverAddress: String = SettingsRepository.DEFAULT_SERVER_ADDRESS,
    val username: String = "",
    val password: String = "",
    val sessionToken: String = "",
    val deviceName: String = SettingsRepository.DEFAULT_DEVICE_NAME,
    val enableRemoteShell: Boolean = SettingsRepository.DEFAULT_ENABLE_REMOTE_SHELL
) {
    /** 规范化后的 base URL，如 http://192.168.1.10:8082；未配置时为空串 */
    val baseUrl: String
        get() {
            var addr = serverAddress.trim().trimEnd('/')
            if (addr.isEmpty()) return ""
            if (!addr.startsWith("http://") && !addr.startsWith("https://")) {
                addr = "http://$addr"
            }
            return addr
        }

    val loggedIn: Boolean get() = sessionToken.isNotEmpty()
}
