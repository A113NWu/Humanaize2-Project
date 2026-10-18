package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.humanaize.aizecompanion.service.PhoneCommandPoller
import com.humanaize.aizecompanion.shell.ShizukuShellExecutor
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel
import kotlinx.coroutines.launch

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

    var permissionState by remember { mutableStateOf(ShizukuShellExecutor.checkPermission()) }
    var testCmd by remember { mutableStateOf("") }
    var testOutput by remember { mutableStateOf("") }
    var running by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // ---- Shizuku 狀態卡 ----
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Shizuku 授權", style = MaterialTheme.typography.titleMedium)
                val statusText = when (permissionState) {
                    null -> "未檢測到 Shizuku 服務（請先安裝並啟動 Shizuku）"
                    false -> "已檢測到 Shizuku，但尚未授權"
                    true -> "已授權，可以 shell 身份執行命令"
                }
                Text(statusText, color = when (permissionState) {
                    true -> MaterialTheme.colorScheme.tertiary
                    else -> MaterialTheme.colorScheme.error
                })
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        scope.launch {
                            val granted = ShizukuShellExecutor.requestPermission()
                            permissionState = ShizukuShellExecutor.checkPermission()
                            if (!granted && permissionState != true) {
                                testOutput = "授權被拒絕或超時"
                            }
                        }
                    }) { Text("請求授權") }
                    OutlinedButton(onClick = {
                        permissionState = ShizukuShellExecutor.checkPermission()
                    }) { Text("刷新狀態") }
                }
            }
        }

        // ---- 遠程命令開關（說明在左、開關固定最右） ----
        Card(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("允許 Aize 遠程執行命令", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "開啟後 PC 端 Aize 可下發 shell 命令到本機執行（需 Shizuku 已授權）",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Switch(
                    checked = settings.enableRemoteShell,
                    onCheckedChange = { viewModel.setRemoteShell(it) }
                )
            }
            val pollerText = when (pollerState) {
                PhoneCommandPoller.State.RUNNING -> "輪詢運行中"
                PhoneCommandPoller.State.NO_SHIZUKU -> "等待 Shizuku 服務…"
                PhoneCommandPoller.State.NO_PERMISSION -> "等待 Shizuku 授權…"
                PhoneCommandPoller.State.SESSION_EXPIRED -> "會話過期，請重新登錄"
                PhoneCommandPoller.State.STOPPED -> "未啟動"
            }
            Text(
                "狀態：$pollerText" + if (pollerActivity.isNotEmpty()) "｜$pollerActivity" else "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 16.dp)
            )
        }

        // ---- 手動測試 ----
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("手動測試", style = MaterialTheme.typography.titleMedium)
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
                    if (running) CircularProgressIndicator(
                        modifier = Modifier.height(16.dp).padding(end = 8.dp), strokeWidth = 2.dp)
                    Text("執行")
                }
                if (testOutput.isNotEmpty()) {
                    Text(
                        testOutput,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}
