package com.humanaize.aizecompanion.service

import android.util.Log
import com.humanaize.aizecompanion.network.AizeApiClient
import com.humanaize.aizecompanion.shell.ShizukuShellExecutor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * 手機命令輪詢器
 *
 * 循環：向 PC 後端 /api/phone/poll 取待執行命令 →
 * 用 Shizuku 執行 → POST /api/phone/result 回傳。
 * 僅在「已配置服務器 + 已登錄（或免登錄）+ 用戶開啟遠程 shell + Shizuku 已授權」時工作。
 */
class PhoneCommandPoller(private val api: AizeApiClient) {

    companion object {
        private const val TAG = "PhoneCmdPoller"
        private const val POLL_INTERVAL_MS = 3000L
        private const val ERROR_BACKOFF_MS = 10_000L
    }

    enum class State { STOPPED, RUNNING, NO_SHIZUKU, NO_PERMISSION, SESSION_EXPIRED }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var job: Job? = null

    private val _state = MutableStateFlow(State.STOPPED)
    val state: StateFlow<State> = _state

    /** 最近一次執行的命令摘要（UI 顯示用） */
    private val _lastActivity = MutableStateFlow("")
    val lastActivity: StateFlow<String> = _lastActivity

    @Volatile
    var deviceName: String = "Android Phone"

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch { loop() }
    }

    fun stop() {
        job?.cancel()
        job = null
        _state.value = State.STOPPED
    }

    private suspend fun loop() {
        var since = 0L
        var backoff = POLL_INTERVAL_MS
        while (true) {
            // Shizuku 狀態檢查
            when (ShizukuShellExecutor.checkPermission()) {
                null -> {
                    _state.value = State.NO_SHIZUKU
                    delay(ERROR_BACKOFF_MS)
                    continue
                }
                false -> {
                    _state.value = State.NO_PERMISSION
                    delay(ERROR_BACKOFF_MS)
                    continue
                }
                true -> Unit
            }

            val result = api.pollPhoneCommands(since, deviceName)
            result.onSuccess { (commands, _) ->
                _state.value = State.RUNNING
                backoff = POLL_INTERVAL_MS
                for (cmd in commands) {
                    since = maxOf(since, cmd.id)
                    _lastActivity.value = "執行: ${cmd.command.take(60)}"
                    val r = ShizukuShellExecutor.execute(
                        cmd.command,
                        timeoutMs = cmd.timeoutSec * 1000L,
                        workDir = cmd.workDir
                    )
                    api.postPhoneResult(
                        id = cmd.id,
                        success = r.success,
                        exitCode = r.exitCode,
                        stdout = r.stdout,
                        stderr = r.stderr,
                        error = r.error,
                        durationMs = r.executionTimeMs
                    )
                    _lastActivity.value = "完成(${r.exitCode}): ${cmd.command.take(50)}"
                }
            }
            result.onFailure { e ->
                if (e is AizeApiClient.SessionExpiredException) {
                    _state.value = State.SESSION_EXPIRED
                    backoff = ERROR_BACKOFF_MS
                } else {
                    Log.w(TAG, "poll failed: ${e.message}")
                    backoff = ERROR_BACKOFF_MS
                }
            }
            delay(backoff)
        }
    }
}
