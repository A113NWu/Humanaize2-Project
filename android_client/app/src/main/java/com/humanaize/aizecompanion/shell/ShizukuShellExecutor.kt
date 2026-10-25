package com.humanaize.aizecompanion.shell

import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import rikka.shizuku.Shizuku
import rikka.shizuku.ShizukuProvider
import java.io.BufferedReader
import java.io.InputStreamReader
import java.lang.reflect.Method
import java.util.concurrent.TimeUnit

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

    /**
     * 授權等待窗口。用戶常常需要切到 Shizuku 應用再點「允許」，
     * 15 秒過短會導致回調被移除、明明已允許卻回報失敗。
     */
    private const val PERMISSION_TIMEOUT_MS = 120_000L

    /** 一次授權請求的結果（比 Boolean 多帶失敗原因，方便 UI 區分展示） */
    enum class PermissionOutcome {
        GRANTED,
        DENIED,
        TIMEOUT,
        SERVICE_UNAVAILABLE,
        ERROR
    }

    data class PermissionRequestResult(
        val outcome: PermissionOutcome,
        val detail: String? = null
    ) {
        val granted: Boolean get() = outcome == PermissionOutcome.GRANTED
    }

    /** 緩存反射得到的 Shizuku.newProcess(String[], String[], String) 方法 */
    @Volatile
    private var newProcessMethod: Method? = null

    /** sticky binder 監聽是否已註冊 */
    @Volatile
    private var binderHooked = false

    /** 應用的 Application Context（用於主動向 Shizuku 重取 binder） */
    @Volatile
    private var appContext: Context? = null

    /** 上次主動向 Shizuku 要求 binder 的時間，避免高頻重複請求 */
    @Volatile
    private var lastBinderRequestAt = 0L

    fun init(context: Context) {
        appContext = context.applicationContext
    }

    /**
     * 主動向 Shizuku 重新索取 binder。
     *
     * 服務在跑、授權也給了，但本進程始終沒收到 binder 時（進程先於服務啟動、
     * 或 Shizuku 沒能在授權後回送），調用 ShizukuProvider 的補救接口可重新觸發一次投遞，
     * 不必重啟整個應用。
     */
    fun requestBinder(force: Boolean = false) {
        val ctx = appContext ?: return
        if (Shizuku.pingBinder()) return
        val now = System.currentTimeMillis()
        if (!force && now - lastBinderRequestAt < 3000L) return
        lastBinderRequestAt = now
        try {
            ShizukuProvider.requestBinderForNonProviderProcess(ctx)
            Log.i(TAG, "requestBinderForNonProviderProcess issued")
        } catch (t: Throwable) {
            Log.w(TAG, "requestBinderForNonProviderProcess failed: ${t.message}")
        }
    }

    /** binder 是否已收到（由監聽回調維護，供 UI/診斷使用） */
    @Volatile
    var binderAlive = false
        private set

    /** binder 狀態變化監聽（UI 用來即時刷新狀態） */
    private val binderStateListeners = java.util.concurrent.CopyOnWriteArrayList<(Boolean) -> Unit>()

    // ---------- 授權請求 ----------

    private val permissionLock = Any()

    /** 當前進行中的授權請求；同一時刻只允許一個，避免重複點擊疊加 listener */
    private var pendingPermission: CompletableDeferred<PermissionOutcome>? = null

    /**
     * 單例授權回調：只在 [ensureInit] 註冊一次。
     * 舊實現每次請求都 new 一個 listener 且從不移除舊的，重複點擊會不斷疊加。
     */
    private val permissionResultListener = object : Shizuku.OnRequestPermissionResultListener {
        override fun onRequestPermissionResult(requestCode: Int, grantResult: Int) {
            if (requestCode != PERMISSION_REQUEST_CODE) return
            val granted = grantResult == PackageManager.PERMISSION_GRANTED
            Log.i(TAG, "onRequestPermissionResult: requestCode=$requestCode grantResult=$grantResult granted=$granted")
            completePending(if (granted) PermissionOutcome.GRANTED else PermissionOutcome.DENIED)
        }
    }

    private fun completePending(outcome: PermissionOutcome) {
        val deferred = synchronized(permissionLock) {
            pendingPermission.also { pendingPermission = null }
        }
        deferred?.complete(outcome)
    }

    fun addBinderStateListener(l: (Boolean) -> Unit) {
        ensureInit()
        binderStateListeners.add(l)
    }

    fun removeBinderStateListener(l: (Boolean) -> Unit) {
        binderStateListeners.remove(l)
    }

    private fun notifyBinderState(alive: Boolean) {
        binderAlive = alive
        binderStateListeners.forEach {
            try { it(alive) } catch (_: Throwable) {}
        }
    }

    /**
     * 註冊 sticky binder 監聽與授權回調（冪等）。
     * 必須在任何 checkSelfPermission / requestPermission 之前調用：
     * transceiver 未就緒時檢查權限會誤報「未授權」，導致已授權卻顯示被拒。
     */
    fun ensureInit() {
        if (binderHooked) return
        synchronized(this) {
            if (binderHooked) return
            try {
                Shizuku.addBinderReceivedListenerSticky {
                    Log.i(TAG, "Shizuku binder received")
                    notifyBinderState(true)
                }
                Shizuku.addBinderDeadListener {
                    Log.w(TAG, "Shizuku binder dead")
                    notifyBinderState(false)
                }
                // 全局只註冊這一個 listener，之後所有請求共用
                Shizuku.addRequestPermissionResultListener(permissionResultListener)
                binderHooked = true
            } catch (t: Throwable) {
                Log.w(TAG, "ensureInit failed: ${t.message}")
            }
        }
    }

    /** 診斷信息：把 Shizuku 各層狀態原樣暴露出來，定位「已授權卻顯示被拒」 */
    fun diagnostics(): String {
        ensureInit()
        fun <T> probe(name: String, block: () -> T): String =
            "$name=" + try { block().toString() } catch (t: Throwable) {
                "THROW ${t.javaClass.simpleName}: ${t.message}"
            }
        return listOf(
            "pingBinder=" + try { Shizuku.pingBinder().toString() } catch (t: Throwable) { "THROW ${t.javaClass.simpleName}: ${t.message}" },
            "binderAlive(flag)=$binderAlive",
            "pendingPermission=${synchronized(permissionLock) { pendingPermission != null }}",
            probe("isPreV11") { Shizuku.isPreV11() },
            probe("serverVersion") { Shizuku.getVersion() },
            probe("serverLatestVersion") { Shizuku.getLatestServiceVersion() },
            probe("checkSelfPermission") { Shizuku.checkSelfPermission() },
            probe("shouldShowRequestPermissionRationale") { Shizuku.shouldShowRequestPermissionRationale() }
        ).joinToString("\n")
    }

    /**
     * Shizuku 應用已安裝時回傳其服務協定版本（如 13），未安裝回 0。
     * 這個值不需要 binder，可用來區分「應用沒裝」與「應用裝了但服務沒啟動」。
     */
    fun latestServiceVersion(): Int = try {
        Shizuku.getLatestServiceVersion()
    } catch (_: Throwable) {
        0
    }

    private fun getNewProcessMethod(): Method? {
        newProcessMethod?.let { return it }
        return try {
            val m = Shizuku::class.java.getDeclaredMethod(
                "newProcess",
                Array<String>::class.java,
                Array<String>::class.java,
                String::class.java
            )
            m.isAccessible = true
            newProcessMethod = m
            m
        } catch (t: Throwable) {
            Log.e(TAG, "Failed to reflect Shizuku.newProcess: ${t.message}")
            null
        }
    }

    /**
     * 檢查 Shizuku 服務是否可用（已安裝、已啟動、已授予權限）
     */
    fun isAvailable(): Boolean {
        ensureInit()
        return try {
            Shizuku.pingBinder()
        } catch (t: Throwable) {
            Log.w(TAG, "Shizuku service unavailable: ${t.message}")
            false
        }
    }

    /**
     * 檢查當前是否已被授予 Shizuku 權限。
     * 阻塞等待 binder 屬 IO 操作，調用方應在 IO 線程執行。
     *
     * @return true=已授予；false=未授予；null=Shizuku 服務不存在
     */
    fun checkPermission(waitMs: Long = 1500L): Boolean? {
        ensureInit()
        return try {
            // 冷啟動時 binder 可能還在路上，短暫等待而不是立即判定「服務不存在」
            var waited = 0L
            while (!Shizuku.pingBinder() && waited < waitMs) {
                Thread.sleep(100L)
                waited += 100L
            }
            if (!Shizuku.pingBinder()) {
                Log.w(TAG, "Shizuku binder not reachable after wait")
                return null
            }
            Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED
        } catch (t: Throwable) {
            Log.w(TAG, "checkPermission error: ${t.message}")
            null
        }
    }

    /**
     * 請求 Shizuku 權限。
     *
     * 初始化與權限檢查在 IO 線程；`Shizuku.requestPermission()` 與 listener 的
     * 註冊/移除都放在主線程（`Dispatchers.Main.immediate`）執行，避免後台線程
     * 啟動授權界面導致彈窗不出現或回調丟失。
     *
     * 超時 120 秒；超時不直接判失敗，先重新 checkSelfPermission，已授權則返回成功。
     */
    suspend fun requestPermission(): PermissionRequestResult {
        ensureInit()

        // 1. 初始化 + 前置檢查（含等待 binder）放在 IO。
        //    點「請求授權」時多等 8 秒：使用者可能剛打開 Shizuku，服務還在啟動。
        val pre = withContext(Dispatchers.IO) { checkPermission(8_000L) }
        when (pre) {
            null -> return PermissionRequestResult(
                PermissionOutcome.SERVICE_UNAVAILABLE,
                "pingBinder=false，Shizuku 服務未啟動"
            )
            true -> return PermissionRequestResult(PermissionOutcome.GRANTED)
            false -> Unit
        }

        val deferred = CompletableDeferred<PermissionOutcome>()
        val alreadyPending = synchronized(permissionLock) {
            if (pendingPermission != null) {
                true
            } else {
                pendingPermission = deferred
                false
            }
        }
        if (alreadyPending) {
            return PermissionRequestResult(PermissionOutcome.ERROR, "已有授權請求正在進行中")
        }

        // 2. 主線程發起授權請求（listener 已在 ensureInit 中註冊，這裡不再重複註冊）
        try {
            withContext(Dispatchers.Main.immediate) {
                Shizuku.requestPermission(PERMISSION_REQUEST_CODE)
            }
        } catch (t: Throwable) {
            Log.e(TAG, "requestPermission failed: ${t.message}", t)
            synchronized(permissionLock) {
                if (pendingPermission === deferred) pendingPermission = null
            }
            return PermissionRequestResult(
                PermissionOutcome.ERROR,
                "${t.javaClass.simpleName}: ${t.message ?: "未知錯誤"}"
            )
        }

        // 3. 等待回調
        val outcome = try {
            withTimeoutOrNull(PERMISSION_TIMEOUT_MS) { deferred.await() }
        } finally {
            synchronized(permissionLock) {
                if (pendingPermission === deferred) pendingPermission = null
            }
        }

        if (outcome != null) {
            return PermissionRequestResult(
                outcome,
                if (outcome == PermissionOutcome.DENIED) "用戶在彈窗中選擇了拒絕" else null
            )
        }

        // 4. 超時：先重新檢查，用戶可能剛好在超時前點了「允許」
        val recheck = withContext(Dispatchers.IO) { checkPermission() }
        return when (recheck) {
            true -> PermissionRequestResult(PermissionOutcome.GRANTED)
            null -> PermissionRequestResult(
                PermissionOutcome.SERVICE_UNAVAILABLE,
                "等待 ${PERMISSION_TIMEOUT_MS / 1000} 秒後 Shizuku 服務不可達"
            )
            false -> PermissionRequestResult(
                PermissionOutcome.TIMEOUT,
                "等待 ${PERMISSION_TIMEOUT_MS / 1000} 秒未收到授權結果"
            )
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

            // 4. 建立 Shizuku 遠程進程（newProcess 為 private，透過反射調用）
            val method = getNewProcessMethod()
            if (method == null) {
                return@withContext ShellResult(
                    success = false, exitCode = -4,
                    stdout = "", stderr = "",
                    error = "無法存取 Shizuku.newProcess 方法，請確認 Shizuku API 版本",
                    executionTimeMs = System.currentTimeMillis() - start
                )
            }
            val dir = workDir ?: "/"
            @Suppress("UNCHECKED_CAST")
            val process = method.invoke(null, cmdArray, envArray, dir) as Process

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
