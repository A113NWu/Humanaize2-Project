package com.humanaize.aizecompanion.ui.screens

import android.content.Context
import android.content.Intent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.humanaize.aizecompanion.service.PhoneCommandPoller
import com.humanaize.aizecompanion.shell.ShizukuShellExecutor
import com.humanaize.aizecompanion.ui.components.AizeCard
import com.humanaize.aizecompanion.ui.components.AizeLayout
import com.humanaize.aizecompanion.ui.components.AizePageScaffold
import com.humanaize.aizecompanion.ui.components.CardSectionTitle
import com.humanaize.aizecompanion.ui.components.CodeBlock
import com.humanaize.aizecompanion.ui.components.InlineNotice
import com.humanaize.aizecompanion.ui.components.SettingRow
import com.humanaize.aizecompanion.ui.components.StatusChip
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Shizuku 頁：授權管理 + 手動測試執行 + 遠程命令開關。
 * 開啟遠程命令後，PC 端 Aize 可下發 shell 到本機執行。
 */
@Composable
fun ShizukuScreen(viewModel: MainViewModel) {
    val settings by viewModel.settings.collectAsState()
    val pollerState by viewModel.pollerState.collectAsState()
    val pollerActivity by viewModel.pollerActivity.collectAsState()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    // Shizuku 是否安裝（用來區分「沒裝」和「裝了但服務沒起/沒授權」）
    val shizukuInstalled = remember {
        try {
            context.packageManager.getPackageInfo("moe.shizuku.privileged.api", 0)
            true
        } catch (_: Throwable) {
            false
        }
    }

    var permissionState by remember { mutableStateOf<Boolean?>(null) }
    var requesting by remember { mutableStateOf(false) }
    var lastFailure by remember { mutableStateOf<String?>(null) }
    var diagExpanded by remember { mutableStateOf(false) }
    var diagInfo by remember { mutableStateOf("") }
    var testCmd by remember { mutableStateOf("") }
    var testOutput by remember { mutableStateOf("") }
    var running by remember { mutableStateOf(false) }

    fun refreshPermission() {
        scope.launch {
            permissionState = withContext(Dispatchers.IO) {
                ShizukuShellExecutor.checkPermission()
            }
        }
    }

    fun openShizukuApp() {
        try {
            val intent = context.packageManager
                .getLaunchIntentForPackage("moe.shizuku.privileged.api")
            if (intent != null) {
                context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
        } catch (_: Throwable) {
        }
    }

    // binder 只在進程啟動時接收一次：若先開本應用、之後才啟動 Shizuku 服務，
    // 必須重啟進程才會重新綁定，否則會一直顯示「服務未運行」。
    fun restartApp() {
        try {
            val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
            if (intent != null) {
                context.startActivity(
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                )
            }
        } catch (_: Throwable) {
        }
        android.os.Process.killProcess(android.os.Process.myPid())
    }

    // 持續輪詢：使用者可能在 Shizuku 裡啟動服務/開授權，狀態要能自己變綠
    LaunchedEffect(Unit) {
        while (true) {
            permissionState = withContext(Dispatchers.IO) {
                ShizukuShellExecutor.checkPermission()
            }
            delay(3000)
        }
    }

    // binder 事件即時刷新（binder 晚到時狀態自動更正，不再誤報）
    DisposableEffect(Unit) {
        val listener: (Boolean) -> Unit = {
            scope.launch {
                permissionState = withContext(Dispatchers.IO) {
                    ShizukuShellExecutor.checkPermission()
                }
            }
        }
        ShizukuShellExecutor.addBinderStateListener(listener)
        onDispose { ShizukuShellExecutor.removeBinderStateListener(listener) }
    }

    // 展開診斷時自動取一次
    LaunchedEffect(diagExpanded) {
        if (diagExpanded) {
            val raw = withContext(Dispatchers.IO) { ShizukuShellExecutor.diagnostics() }
            diagInfo = raw +
                    "\npackageName=${context.packageName}" +
                    "\nshizukuInstalled=$shizukuInstalled"
        }
    }

    val statusLabel = when (permissionState) {
        true -> "已授權"
        false -> "未授權"
        null -> "服務未運行"
    }
    val statusColor: Color = when (permissionState) {
        true -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.error
    }

    AizePageScaffold(
        title = "Shizuku",
        statusText = statusLabel,
        statusColor = statusColor
    ) { innerPadding ->

        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(AizeLayout.ScreenPadding),
            verticalArrangement = Arrangement.spacedBy(AizeLayout.CardSpacing)
        ) {
            // ---- 授權狀態 ----
            AizeCard {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        CardSectionTitle("授權狀態")
                        Text(
                            when (permissionState) {
                                true -> "已取得權限，可執行 shell 命令"
                                false -> "已檢測到 Shizuku 服務，但本應用尚未授權"
                                null -> if (!shizukuInstalled) {
                                    "未檢測到 Shizuku，請先安裝並啟動 Shizuku"
                                } else {
                                    "Shizuku 已安裝，但本應用沒收到它的服務。" +
                                            "請確認 Shizuku 應用頂部顯示「服務正在運行」；" +
                                            "若是剛剛才啟動服務，請點下方「重啟應用」重新連接（包名 ${context.packageName}）"
                                }
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    StatusChip(statusLabel, statusColor)
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = {
                            scope.launch {
                                requesting = true
                                lastFailure = null
                                val result = ShizukuShellExecutor.requestPermission()
                                // 請求結束後統一刷新一次狀態
                                permissionState = withContext(Dispatchers.IO) {
                                    ShizukuShellExecutor.checkPermission()
                                }
                                requesting = false
                                if (!result.granted) {
                                    lastFailure = when (result.outcome) {
                                        ShizukuShellExecutor.PermissionOutcome.DENIED ->
                                            "授權被拒絕。如屬誤點，請重新請求授權。"
                                        ShizukuShellExecutor.PermissionOutcome.TIMEOUT ->
                                            "等待授權超時（120 秒）。若已在 Shizuku 中允許，請點「刷新狀態」。"
                                        ShizukuShellExecutor.PermissionOutcome.SERVICE_UNAVAILABLE ->
                                            "Shizuku 服務未啟動或不可達，請先在 Shizuku 應用中啟動服務。"
                                        ShizukuShellExecutor.PermissionOutcome.ERROR ->
                                            result.detail ?: "請求授權失敗"
                                        ShizukuShellExecutor.PermissionOutcome.GRANTED -> null
                                    }
                                }
                            }
                        },
                        enabled = !requesting
                    ) {
                        if (requesting) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp,
                                color = MaterialTheme.colorScheme.onPrimary
                            )
                            Spacer(Modifier.width(8.dp))
                            Text("等待授權…")
                        } else {
                            Text("請求授權")
                        }
                    }
                    OutlinedButton(
                        onClick = { refreshPermission() },
                        enabled = !requesting
                    ) {
                        Icon(
                            Icons.Default.Refresh,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(Modifier.width(6.dp))
                        Text("刷新狀態")
                    }
                }

                // 第二行：避免三個按鈕擠在一行被壓成直排文字
                if (shizukuInstalled) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { openShizukuApp() }) {
                            Icon(
                                Icons.Default.PlayArrow,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(Modifier.width(6.dp))
                            Text("開啟 Shizuku")
                        }
                        if (permissionState == null) {
                            OutlinedButton(onClick = { restartApp() }) {
                                Icon(
                                    Icons.Default.Refresh,
                                    contentDescription = null,
                                    modifier = Modifier.size(18.dp)
                                )
                                Spacer(Modifier.width(6.dp))
                                Text("重啟應用")
                            }
                        }
                    }
                }

                lastFailure?.let { msg ->
                    InlineNotice(text = msg, icon = Icons.Default.ErrorOutline)
                }

                TextButton(onClick = { diagExpanded = !diagExpanded }) {
                    Icon(
                        imageVector = if (diagExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(if (diagExpanded) "收起診斷信息" else "顯示診斷信息")
                }
                AnimatedVisibility(visible = diagExpanded) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        CodeBlock(if (diagInfo.isEmpty()) "讀取中…" else diagInfo)
                        TextButton(onClick = {
                            scope.launch {
                                diagInfo = withContext(Dispatchers.IO) {
                                    ShizukuShellExecutor.diagnostics()
                                }
                            }
                        }) {
                            Icon(
                                Icons.Default.Refresh,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(Modifier.width(6.dp))
                            Text("重新檢測")
                        }
                    }
                }
            }

            // ---- 遠程命令開關（說明在左、開關固定最右） ----
            AizeCard {
                CardSectionTitle("遠程命令")
                SettingRow(
                    title = "允許 Aize 遠程執行命令",
                    subtitle = "開啟後 PC 端 Aize 可下發 shell 命令到本機執行（需 Shizuku 已授權）",
                    control = {
                        Switch(
                            checked = settings.enableRemoteShell,
                            onCheckedChange = { viewModel.setRemoteShell(it) }
                        )
                    }
                )
                Divider(color = MaterialTheme.colorScheme.outlineVariant)
                val pollerText = when (pollerState) {
                    PhoneCommandPoller.State.RUNNING -> "輪詢運行中"
                    PhoneCommandPoller.State.NO_SHIZUKU -> "等待 Shizuku 服務"
                    PhoneCommandPoller.State.NO_PERMISSION -> "等待 Shizuku 授權"
                    PhoneCommandPoller.State.SESSION_EXPIRED -> "會話過期"
                    PhoneCommandPoller.State.STOPPED -> "未啟動"
                }
                val pollerColor = when (pollerState) {
                    PhoneCommandPoller.State.RUNNING -> MaterialTheme.colorScheme.tertiary
                    PhoneCommandPoller.State.STOPPED -> MaterialTheme.colorScheme.onSurfaceVariant
                    else -> MaterialTheme.colorScheme.error
                }
                SettingRow(
                    title = "輪詢狀態",
                    subtitle = pollerActivity.ifEmpty { "尚無執行記錄" },
                    control = { StatusChip(pollerText, pollerColor) }
                )
            }

            // ---- 手動測試 ----
            AizeCard {
                CardSectionTitle("手動測試")
                OutlinedTextField(
                    value = testCmd,
                    onValueChange = { testCmd = it },
                    label = { Text("shell 命令") },
                    placeholder = { Text("dumpsys battery | grep level") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Button(
                    onClick = {
                        scope.launch {
                            running = true
                            val r = ShizukuShellExecutor.execute(testCmd)
                            testOutput = buildString {
                                append("exit=${r.exitCode} (${r.executionTimeMs}ms)\n")
                                if (r.stdout.isNotEmpty()) append(r.stdout)
                                if (r.stderr.isNotEmpty()) append("\n[stderr]\n${r.stderr}")
                                r.error?.let { append("\n[error] $it") }
                            }.trim()
                            running = false
                        }
                    },
                    enabled = testCmd.isNotBlank() && !running && permissionState == true
                ) {
                    if (running) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                        Spacer(Modifier.width(8.dp))
                    } else {
                        Icon(
                            Icons.Default.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(Modifier.width(6.dp))
                    }
                    Text(if (running) "執行中…" else "執行")
                }
                if (testOutput.isNotEmpty()) {
                    CodeBlock(
                        text = testOutput,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }
        }
    }
}
