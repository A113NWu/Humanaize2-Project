package com.humanaize.aizecompanion.shell

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import rikka.shizuku.Shizuku
import rikka.shizuku.ShizukuRemoteProcess
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * 執行結果封裝
 */
data class ShellResult(
    val success: Boolean,
    val exitCode: Int,
    val stdout: String,
    val stderr: String,
    val error: String? = null,
    val executionTimeMs: Long = 0L
)

/**
 * Shizuku Shell 執行器
 *
 * 透過 Shizuku 服務取得 ADB Shell 級別權限，執行任意 shell 命令。
 * 流程：
 *   1. 檢查 Shizuku 是否安裝且服務已啟動
 *   2. 請求/驗證權限授予（透過 binder 向 Shizuku 管理員請求）
 *   3. 使用 Shizuku.newProcess(cmd) 啟動遠程 shell 進程
 *   4. 讀取 stdout/stderr，等待退出碼，返回結果
 */
object ShizukuShellExecutor {

    private const val TAG = "ShizukuShell"
    private const val DEFAULT_TIMEOUT_MS = 30_000L
    private const val PERMISSION_REQUEST_CODE = 10001

    private val permissionCallbackInvoked = AtomicBoolean(false)

    /**
     * 檢查 Shizuku 服務是否可用（已安裝、已啟動、已授予權限）
     */
    fun isAvailable(): Boolean {
        return try {
            Shizuku.pingBinder()
        } catch (t: Throwable) {
            Log.w(TAG, "Shizuku service unavailable: ${t.message}")
            false
        }
    }

    /**
     * 檢查當前是否已被授予 Shizuku 權限
     * @return true=已授予；false=未授予；null=Shizuku 服務不存在
     */
    fun checkPermission(): Boolean? {
        return try {
            if (!Shizuku.pingBinder()) {
                Log.w(TAG, "Shizuku binder not reachable")
                return null
            }
            // Shizuku.checkSelfPermission: 0=GRANTED, -1=DENIED
            Shizuku.checkSelfPermission() == 0
        } catch (t: Throwable) {
            Log.w(TAG, "checkPermission error: ${t.message}")
            null
        }
    }

    /**
     * 請求 Shizuku 權限（需要 Activity 上下文，實際在 UI 層調用）
     * 此處僅提供一次性的異步請求接口
     */
    suspend fun requestPermission(): Boolean = withContext(Dispatchers.IO) {
        suspendCancellableCoroutine { cont ->
            try {
                if (!Shizuku.pingBinder()) {
                    cont.resume(false)
                    return@suspendCancellableCoroutine
                }
                if (Shizuku.checkSelfPermission() == 0) {
                    cont.resume(true)
                    return@suspendCancellableCoroutine
                }
                permissionCallbackInvoked.set(false)

                val listener = object : Shizuku.OnRequestPermissionResultListener {
                    override fun onRequestPermissionResult(requestCode: Int, grantResult: Int) {
                        if (requestCode != PERMISSION_REQUEST_CODE) return
                        Shizuku.removeRequestPermissionResultListener(this)
                        permissionCallbackInvoked.set(true)
                        cont.resume(grantResult == 0)
                    }
                }
                Shizuku.addRequestPermissionResultListener(listener)

                cont.invokeOnCancellation {
                    try {
                        Shizuku.removeRequestPermissionResultListener(listener)
                    } catch (_: Throwable) {}
                }

                Shizuku.requestPermission(PERMISSION_REQUEST_CODE)

                // 兜底：15 秒內未回調則視為失敗
                Thread {
                    try {
                        Thread.sleep(15_000L)
                        if (!permissionCallbackInvoked.getAndSet(true)) {
                            try {
                                Shizuku.removeRequestPermissionResultListener(listener)
                            } catch (_: Throwable) {}
                            if (cont.isActive) cont.resume(false)
                        }
                    } catch (_: Throwable) {}
                }.start()
            } catch (t: Throwable) {
                Log.e(TAG, "requestPermission failed: ${t.message}")
                cont.resumeWithException(t)
            }
        }
    }

    /**
     * 執行 shell 命令（預設透過 sh -c 包裝，支援管道/重定向）
     *
     * @param command 完整 shell 命令，例如："ls -la /sdcard" 或 "pm list packages"
     * @param timeoutMs 超時毫秒；0 或負數使用預設 30s
     * @param workDir 工作目錄；null 表示 /
     * @param envVars 額外環境變數；可為 null
     */
    suspend fun execute(
        command: String,
        timeoutMs: Long = DEFAULT_TIMEOUT_MS,
        workDir: String? = null,
        envVars: Map<String, String>? = null
    ): ShellResult = withContext(Dispatchers.IO) {
        val start = System.currentTimeMillis()

        // 1. 可用性檢查
        val permissionStatus = checkPermission()
        if (permissionStatus == null) {
            return@withContext ShellResult(
                success = false, exitCode = -1,
                stdout = "", stderr = "",
                error = "Shizuku 服務未安裝或未啟動，請先安裝並啟動 Shizuku",
                executionTimeMs = System.currentTimeMillis() - start
            )
        }
        if (permissionStatus == false) {
            return@withContext ShellResult(
                success = false, exitCode = -2,
                stdout = "", stderr = "",
                error = "尚未授予 Shizuku 權限，請在彈窗中點擊允許",
                executionTimeMs = System.currentTimeMillis() - start
            )
        }

        val effTimeout = if (timeoutMs > 0) timeoutMs else DEFAULT_TIMEOUT_MS

        try {
            // 2. 組裝命令：用 sh -c 包裹以支援管道/變數展開
            val cmdArray = arrayOf("sh", "-c", command)

            // 3. 環境變數轉換
            val envArray: Array<String>? = envVars?.let {
                it.map { (k, v) -> "$k=$v" }.toTypedArray()
            }

            // 4. 建立 Shizuku 遠程進程
            val process: ShizukuRemoteProcess = if (workDir != null) {
                Shizuku.newProcess(cmdArray, envArray, workDir)
            } else {
                Shizuku.newProcess(cmdArray, envArray)
            }

            // 5. 讀取 stdout/stderr（分離線程防止阻塞）
            val stdoutBuilder = StringBuilder()
            val stderrBuilder = StringBuilder()

            val stdoutThread = Thread {
                try {
                    BufferedReader(InputStreamReader(process.inputStream)).useLines { lines ->
                        lines.forEach { line ->
                            synchronized(stdoutBuilder) {
                                stdoutBuilder.append(line).append('\n')
                            }
                        }
                    }
                } catch (t: Throwable) {
                    Log.w(TAG, "read stdout error: ${t.message}")
                }
            }

            val stderrThread = Thread {
                try {
                    BufferedReader(InputStreamReader(process.errorStream)).useLines { lines ->
                        lines.forEach { line ->
                            synchronized(stderrBuilder) {
                                stderrBuilder.append(line).append('\n')
                            }
                        }
                    }
                } catch (t: Throwable) {
                    Log.w(TAG, "read stderr error: ${t.message}")
                }
            }

            stdoutThread.start()
            stderrThread.start()

            // 6. 等待進程結束（帶超時）
            val finished = process.waitFor(effTimeout, TimeUnit.MILLISECONDS)

            val exitCode = if (finished) {
                process.exitValue()
            } else {
                // 超時：強制殺掉進程
                try { process.destroyForcibly() } catch (_: Throwable) {}
                try { process.destroy() } catch (_: Throwable) {}
                -99
            }

            stdoutThread.join(2000L)
            stderrThread.join(2000L)

            // 7. 組裝結果
            val stdout = synchronized(stdoutBuilder) { stdoutBuilder.toString().trimEnd('\n') }
            val stderr = synchronized(stderrBuilder) { stderrBuilder.toString().trimEnd('\n') }

            ShellResult(
                success = (exitCode == 0),
                exitCode = exitCode,
                stdout = stdout,
                stderr = stderr,
                error = if (!finished) "命令執行超時（${effTimeout}ms）" else null,
                executionTimeMs = System.currentTimeMillis() - start
            )
        } catch (t: Throwable) {
            Log.e(TAG, "execute command failed: ${t.message}", t)
            ShellResult(
                success = false, exitCode = -3,
                stdout = "", stderr = "",
                error = "執行異常: ${t.message}",
                executionTimeMs = System.currentTimeMillis() - start
            )
        }
    }

    /**
     * 便捷方法：執行多條命令（用 ; 連接）
     */
    suspend fun executeMultiple(
        commands: List<String>,
        timeoutMs: Long = DEFAULT_TIMEOUT_MS
    ): ShellResult {
        return execute(commands.joinToString(" ; "), timeoutMs)
    }

    /**
     * 便捷方法：執行 pm（Package Manager）命令
     */
    suspend fun pm(args: String, timeoutMs: Long = 15_000L): ShellResult {
        return execute("pm $args", timeoutMs)
    }

    /**
     * 便捷方法：執行 am（Activity Manager）命令
     */
    suspend fun am(args: String, timeoutMs: Long = 15_000L): ShellResult {
        return execute("am $args", timeoutMs)
    }

    /**
     * 便捷方法：執行 settings 命令
     */
    suspend fun settings(args: String, timeoutMs: Long = 10_000L): ShellResult {
        return execute("settings $args", timeoutMs)
    }
}
