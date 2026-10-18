package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 設定頁：服務器、設備名、遠程 shell、賬號管理。
 * 開關統一排版：說明文字在左，開關固定同一行最右側。
 */
@Composable
fun SettingsScreen(viewModel: MainViewModel) {
    val settings by viewModel.settings.collectAsState()

    var server by remember(settings.serverAddress) { mutableStateOf(settings.serverAddress) }
    var deviceName by remember(settings.deviceName) { mutableStateOf(settings.deviceName) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // ---- 連接 ----
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("連接", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(
                    value = server,
                    onValueChange = {
                        server = it
                        viewModel.saveServerAddress(it)
                    },
                    label = { Text("服務器地址") },
                    placeholder = { Text("192.168.1.10:8082") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = deviceName,
                    onValueChange = {
                        deviceName = it
                        viewModel.saveDeviceName(it)
                    },
                    label = { Text("設備名稱") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Text(
                    "登錄狀態：" + if (settings.loggedIn) "已登錄" else "未登錄",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (settings.loggedIn) MaterialTheme.colorScheme.tertiary
                    else MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (settings.loggedIn) {
                    OutlinedButton(onClick = { viewModel.logout() }) { Text("登出") }
                }
            }
        }

        // ---- 功能開關 ----
        Card(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("遠程 Shell（Shizuku）", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "允許 PC 端 Aize 在本機執行 shell 命令",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Switch(
                    checked = settings.enableRemoteShell,
                    onCheckedChange = { viewModel.setRemoteShell(it) }
                )
            }
        }

        // ---- 關於 ----
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("關於", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Aize Companion — Humanaize2 手機伴侶\n" +
                            "對話 · Live2D · Shizuku 遠程 Shell",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}
