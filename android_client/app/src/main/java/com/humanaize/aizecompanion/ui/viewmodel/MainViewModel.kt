package com.humanaize.aizecompanion.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.humanaize.aizecompanion.AizeApplication
import com.humanaize.aizecompanion.data.AppSettings
import com.humanaize.aizecompanion.network.AizeApiClient
import com.humanaize.aizecompanion.service.PhoneCommandPoller
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** 聊天列表項：用戶消息 / Aize 回覆 / 思考·技能日誌行 */
data class ChatItem(
    val id: Long,
    val role: Role,
    var text: String,
    val logKind: String? = null
) {
    enum class Role { USER, ASSISTANT, LOG }
}

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val app = application as AizeApplication
    val api: AizeApiClient get() = app.apiClient
    private val repo = app.settingsRepository

    val settings: StateFlow<AppSettings> = repo.settingsFlow
        .stateIn(viewModelScope, SharingStarted.Eagerly, AppSettings())

    val pollerState: StateFlow<PhoneCommandPoller.State> = app.commandPoller.state
    val pollerActivity: StateFlow<String> = app.commandPoller.lastActivity

    // ---------- 登錄 ----------

    sealed class LoginState {
        object Idle : LoginState()
        object Busy : LoginState()
        data class Ok(val authFree: Boolean) : LoginState()
        data class Fail(val message: String) : LoginState()
    }

    private val _loginState = MutableStateFlow<LoginState>(LoginState.Idle)
    val loginState: StateFlow<LoginState> = _loginState

    fun login(server: String, username: String, password: String) {
        viewModelScope.launch {
            _loginState.value = LoginState.Busy
            repo.updateServerAddress(server)
            api.updateConfig(AppSettings(serverAddress = server).baseUrl, "")
            api.login(username, password)
                .onSuccess { token ->
                    repo.updateCredentials(username, password)
                    // 免登錄模式後端忽略 Authorization；存標記位讓 UI 視為已連接
                    repo.updateSessionToken(token.ifEmpty { "AUTHFREE" })
                    _loginState.value = LoginState.Ok(authFree = token.isEmpty())
                }
                .onFailure { e ->
                    _loginState.value = LoginState.Fail(e.message ?: "登錄失敗")
                }
        }
    }

    fun logout() {
        viewModelScope.launch {
            repo.updateSessionToken("")
            _loginState.value = LoginState.Idle
        }
    }

    fun resetLoginState() {
        _loginState.value = LoginState.Idle
    }

    // ---------- 設定 ----------

    fun saveServerAddress(addr: String) = viewModelScope.launch { repo.updateServerAddress(addr) }
    fun saveDeviceName(name: String) = viewModelScope.launch { repo.updateDeviceName(name) }
    fun setRemoteShell(enabled: Boolean) = viewModelScope.launch { repo.updateEnableRemoteShell(enabled) }

    // ---------- 聊天 ----------

    private val _messages = MutableStateFlow<List<ChatItem>>(emptyList())
    val messages: StateFlow<List<ChatItem>> = _messages

    private val _sending = MutableStateFlow(false)
    val sending: StateFlow<Boolean> = _sending

    private var nextId = 1L

    fun sendChat(text: String) {
        val msg = text.trim()
        if (msg.isEmpty() || _sending.value) return
        viewModelScope.launch {
            _sending.value = true
            appendItem(ChatItem(nextId++, ChatItem.Role.USER, msg))
            val replyItem = ChatItem(nextId++, ChatItem.Role.ASSISTANT, "")
            appendItem(replyItem)
            try {
                api.chatStream(msg).collect { ev ->
                    when (ev) {
                        is AizeApiClient.ChatEvent.Text -> {
                            replyItem.text += ev.content
                            touchItem(replyItem.id)
                        }
                        is AizeApiClient.ChatEvent.Log -> {
                            if (ev.content.isNotBlank()) {
                                appendItem(ChatItem(nextId++, ChatItem.Role.LOG, ev.content.trimEnd(), ev.kind))
                            }
                        }
                        is AizeApiClient.ChatEvent.Error -> {
                            replyItem.text = ev.message
                            touchItem(replyItem.id)
                        }
                        AizeApiClient.ChatEvent.Done -> Unit
                    }
                }
            } catch (e: Exception) {
                if (replyItem.text.isEmpty()) {
                    replyItem.text = "連接失敗: ${e.message}"
                    touchItem(replyItem.id)
                }
            }
            if (replyItem.text.isEmpty()) {
                replyItem.text = "（無回覆）"
                touchItem(replyItem.id)
            }
            _sending.value = false
        }
    }

    fun clearChat() {
        _messages.value = emptyList()
    }

    private fun appendItem(item: ChatItem) {
        _messages.value = _messages.value + item
    }

    /** 原地更新後觸發重組（text 是 var） */
    private fun touchItem(id: Long) {
        _messages.value = _messages.value.map { if (it.id == id) it.copy() else it }
    }
}
