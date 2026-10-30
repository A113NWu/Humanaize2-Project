package com.humanaize.aizecompanion.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.humanaize.aizecompanion.AizeApplication
import com.humanaize.aizecompanion.data.AppSettings
import com.humanaize.aizecompanion.network.AizeApiClient
import com.humanaize.aizecompanion.service.AizeNotifier
import com.humanaize.aizecompanion.service.PhoneCommandPoller
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
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
    val logKind: String? = null,
    val time: Long = System.currentTimeMillis()
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
    private var streamJob: Job? = null
    private var streamToken = 0
    /** 被打斷的流 token：這種取消不顯示「連接失敗」 */
    private var suppressErrorForToken = -1
    private var clearedBefore = 0L
    private var lastLocalSendAt = 0L
    private var baselineLoaded = false
    private val seenTurns = mutableSetOf<String>()
    private val turnItemIds = mutableMapOf<String, Long>()
    private var timelineItemId = 900_000L
    /** 主動消息不在時間線裡，單獨保留，重建列表時一起拼回去 */
    private val extraItems = mutableListOf<ChatItem>()

    init {
        // 每 8 秒同步服務器時間線：Aize 重開 App 後仍有完整歷史，
        // 也能收到她在別處（網頁/CLI）產生的回覆
        viewModelScope.launch {
            while (true) {
                if (api.configured) runCatching { refreshTimeline(notify = true) }
                delay(8_000)
            }
        }
        // SSE 主動消息：Aize 主動找主人說話時立刻顯示並通知
        viewModelScope.launch {
            while (true) {
                if (api.configured) {
                    try {
                        api.eventStream().collect { ev ->
                            if (ev.type == "autonomous") {
                                val item = ChatItem(nextId++, ChatItem.Role.ASSISTANT, ev.content)
                                extraItems += item
                                appendItem(item)
                                AizeNotifier.notify(getApplication(), ev.content)
                            }
                        }
                    } catch (e: CancellationException) {
                        throw e
                    } catch (_: Exception) {
                        // 斷線後 5 秒重連
                    }
                }
                delay(5_000)
            }
        }
    }

    fun sendChat(text: String) {
        val msg = text.trim()
        if (msg.isEmpty()) return
        // 用戶消息立刻上屏；是否打斷由 PC 端子 Agent 判斷（和網頁端同一套邏輯）
        appendItem(ChatItem(nextId++, ChatItem.Role.USER, msg))
        lastLocalSendAt = System.currentTimeMillis() / 1000
        val active = streamJob?.isActive == true
        viewModelScope.launch {
            var interrupted = false
            if (active) {
                val verdict = api.requestInterrupt(msg).getOrNull()
                if (verdict == null || verdict.interrupt || verdict.idle) {
                    interrupted = true
                    suppressErrorForToken = streamToken
                    api.cancelActiveChat()
                    streamJob?.join() // 等舊流關閉，服務端釋放聊天鎖
                } else {
                    // 子 Agent 判定「先講完」：排隊等當前回覆結束再發
                    streamJob?.join()
                }
            }
            startStream(msg, settleMs = if (interrupted) 600 else 0)
        }
    }

    private fun startStream(msg: String, settleMs: Long) {
        val token = ++streamToken
        streamJob = viewModelScope.launch {
            if (settleMs > 0) delay(settleMs)
            _sending.value = true
            val replyItem = ChatItem(nextId++, ChatItem.Role.ASSISTANT, "")
            appendItem(replyItem)
            var attempt = 0
            try {
                while (true) {
                    var busy = false
                    api.chatStream(msg).collect { ev ->
                        when (ev) {
                            is AizeApiClient.ChatEvent.Text -> {
                                replyItem.text += ev.content
                                touchItem(replyItem.id)
                            }
                            // 思考/技能日誌不再顯示（避免刷屏）
                            is AizeApiClient.ChatEvent.Log -> Unit
                            is AizeApiClient.ChatEvent.Error -> {
                                replyItem.text = ev.message
                                touchItem(replyItem.id)
                            }
                            AizeApiClient.ChatEvent.Busy -> busy = true
                            AizeApiClient.ChatEvent.Done -> Unit
                        }
                    }
                    if (!busy) break
                    attempt++
                    if (attempt >= 3) {
                        replyItem.text = "Aize 還在忙，請稍後再試"
                        touchItem(replyItem.id)
                        break
                    }
                    delay(1_200L * attempt)
                }
                if (replyItem.text.isEmpty()) {
                    replyItem.text = "（無回覆）"
                    touchItem(replyItem.id)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (token == suppressErrorForToken) {
                    // 主動打斷造成的取消，不顯示連接錯誤
                    if (replyItem.text.isEmpty()) removeItem(replyItem.id)
                } else if (replyItem.text.isEmpty()) {
                    replyItem.text = "連接失敗: ${e.message}"
                    touchItem(replyItem.id)
                }
            } finally {
                if (token == streamToken) _sending.value = false
            }
        }
    }

    /** 從服務器時間線重建列表（只在本地沒有正在流式輸出時覆蓋） */
    private suspend fun refreshTimeline(notify: Boolean) {
        if (_sending.value) return
        val turns = api.fetchTimeline().getOrNull() ?: return
        if (_sending.value) return
        val visible = turns.filter { it.ts >= clearedBefore }

        // 通知：新出現的 Aize 回覆（自己剛發的輪次不重複提醒）
        if (notify && baselineLoaded) {
            visible.forEach { t ->
                val skip = lastLocalSendAt > 0 && t.ts - lastLocalSendAt < 90
                if (t.id !in seenTurns && t.text.isNotBlank() && !skip) {
                    AizeNotifier.notify(getApplication(), t.text)
                }
            }
        }
        visible.forEach { seenTurns += it.id }
        baselineLoaded = true

        val items = mutableListOf<ChatItem>()
        visible.forEach { t ->
            if (t.user.isNotBlank()) {
                items += ChatItem(itemId(t.id, "u"), ChatItem.Role.USER, t.user, time = t.ts * 1000)
            }
            if (t.text.isNotBlank()) {
                items += ChatItem(itemId(t.id, "a"), ChatItem.Role.ASSISTANT, t.text, time = t.ts * 1000)
            }
        }
        items += extraItems.filter { it.time >= clearedBefore * 1000 }
        _messages.value = items
    }

    private fun itemId(turnId: String, suffix: String): Long =
        turnItemIds.getOrPut("$turnId|$suffix") { timelineItemId++ }

    fun clearChat() {
        _messages.value = emptyList()
        // 只隱藏此刻之前的歷史，之後的新回覆照常顯示
        clearedBefore = System.currentTimeMillis() / 1000
    }

    private fun appendItem(item: ChatItem) {
        _messages.value = _messages.value + item
    }

    /** 原地更新後觸發重組（text 是 var） */
    private fun touchItem(id: Long) {
        _messages.value = _messages.value.map { if (it.id == id) it.copy() else it }
    }

    private fun removeItem(id: Long) {
        _messages.value = _messages.value.filterNot { it.id == id }
    }
}
