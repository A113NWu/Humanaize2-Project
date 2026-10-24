package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.humanaize.aizecompanion.BuildConfig
import com.humanaize.aizecompanion.ui.components.AizeCard
import com.humanaize.aizecompanion.ui.components.AizeLayout
import com.humanaize.aizecompanion.ui.components.AizePageScaffold
import com.humanaize.aizecompanion.ui.components.CardSectionTitle
import com.humanaize.aizecompanion.ui.components.SettingRow
import com.humanaize.aizecompanion.ui.components.StatusChip
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 設定頁：分組卡片（連接 / 語音 / 關於）。
 * 每行統一「標題 + 副標題在左，控件固定最右」。
 */
@Composable
fun SettingsScreen(viewModel: MainViewModel) {
    val settings by viewModel.settings.collectAsState()

    var server by remember(settings.serverAddress) { mutableStateOf(settings.serverAddress) }
    var deviceName by remember(settings.deviceName) { mutableStateOf(settings.deviceName) }

    AizePageScaffold(
        title = "設定",
        statusText = if (settings.loggedIn) "已登錄" else "未登錄",
        statusColor = if (settings.loggedIn) MaterialTheme.colorScheme.tertiary
        else MaterialTheme.colorScheme.error
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(AizeLayout.ScreenPadding),
            verticalArrangement = Arrangement.spacedBy(AizeLayout.CardSpacing)
        ) {
            // ---- 連接 ----
            AizeCard {
                CardSectionTitle("連接")
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
                Divider(color = MaterialTheme.colorScheme.outlineVariant)
                SettingRow(
                    title = "登錄狀態",
                    subtitle = if (settings.loggedIn) {
                        "賬號：${settings.username.ifEmpty { "免登錄模式" }}"
                    } else {
                        "尚未連接到 PC 端"
                    },
                    control = {
                        StatusChip(
                            text = if (settings.loggedIn) "已連接" else "未連接",
                            color = if (settings.loggedIn) MaterialTheme.colorScheme.tertiary
                            else MaterialTheme.colorScheme.error
                        )
                    }
                )
                if (settings.loggedIn) {
                    OutlinedButton(
                        onClick = { viewModel.logout() },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("登出")
                    }
                }
            }

            // ---- 語音 ----
            AizeCard {
                CardSectionTitle("語音")
                SettingRow(
                    title = "語音播報",
                    subtitle = "由 PC 端 Live2D 頁面觸發 speak 命令，手機端負責播放",
                    control = {
                        Icon(
                            Icons.Default.VolumeUp,
                            contentDescription = null,
                            modifier = Modifier.size(22.dp),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                )
                Divider(color = MaterialTheme.colorScheme.outlineVariant)
                SettingRow(
                    title = "音頻自動播放",
                    subtitle = "WebView 已允許無需手勢播放，避免語音被攔截",
                    control = {
                        StatusChip(
                            text = "已開啟",
                            color = MaterialTheme.colorScheme.tertiary
                        )
                    }
                )
            }

            // ---- 關於 ----
            AizeCard {
                CardSectionTitle("關於")
                SettingRow(
                    title = "Aize Companion",
                    subtitle = "Humanaize2 手機伴侶",
                    control = {
                        StatusChip(
                            text = "v${BuildConfig.VERSION_NAME}",
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                )
                Divider(color = MaterialTheme.colorScheme.outlineVariant)
                SettingRow(
                    title = "功能",
                    subtitle = "對話 · Live2D · Shizuku 遠程 Shell"
                )
            }
        }
    }
}
