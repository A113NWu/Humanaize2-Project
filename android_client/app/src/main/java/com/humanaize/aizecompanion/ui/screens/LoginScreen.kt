package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.outlined.Dns
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.humanaize.aizecompanion.ui.components.AizeLayout
import com.humanaize.aizecompanion.ui.components.InlineNotice
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 登錄頁：填 PC 服務器地址 + Web 賬號密碼，
 * POST /api/login 拿到 session 後進入主界面。
 */
@Composable
fun LoginScreen(viewModel: MainViewModel) {
    val settings by viewModel.settings.collectAsState()
    val loginState by viewModel.loginState.collectAsState()

    var server by remember(settings.serverAddress) { mutableStateOf(settings.serverAddress) }
    var username by remember(settings.username) { mutableStateOf(settings.username) }
    var password by remember(settings.password) { mutableStateOf(settings.password) }
    var passwordVisible by remember { mutableStateOf(false) }

    val busy = loginState is MainViewModel.LoginState.Busy

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .systemBarsPadding()
            .imePadding()
            .padding(AizeLayout.ScreenPadding),
        contentAlignment = Alignment.Center
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .widthIn(max = 420.dp),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 3.dp)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Outlined.Dns,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(28.dp)
                    )
                    Spacer(Modifier.size(10.dp))
                    Column {
                        Text(
                            "連接到你的 Aize",
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            "填 PC 端 Humanaize2 的局域網地址與 Web 賬號",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Spacer(Modifier.height(4.dp))

                OutlinedTextField(
                    value = server,
                    onValueChange = { server = it },
                    label = { Text("服務器地址") },
                    placeholder = { Text("192.168.1.10:8082") },
                    leadingIcon = { Icon(Icons.Outlined.Dns, contentDescription = null) },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = username,
                    onValueChange = { username = it },
                    label = { Text("賬號") },
                    leadingIcon = { Icon(Icons.Outlined.Person, contentDescription = null) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("密碼") },
                    leadingIcon = { Icon(Icons.Outlined.Lock, contentDescription = null) },
                    trailingIcon = {
                        IconButton(onClick = { passwordVisible = !passwordVisible }) {
                            Icon(
                                imageVector = if (passwordVisible) Icons.Outlined.VisibilityOff
                                else Icons.Outlined.Visibility,
                                contentDescription = if (passwordVisible) "隱藏密碼" else "顯示密碼"
                            )
                        }
                    },
                    singleLine = true,
                    isError = loginState is MainViewModel.LoginState.Fail,
                    visualTransformation = if (passwordVisible) VisualTransformation.None
                    else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth()
                )

                // 錯誤內聯顯示在卡片內
                (loginState as? MainViewModel.LoginState.Fail)?.let { fail ->
                    InlineNotice(text = fail.message, icon = Icons.Default.ErrorOutline)
                }

                Button(
                    onClick = { viewModel.login(server, username, password) },
                    enabled = !busy && server.isNotBlank(),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp)
                ) {
                    if (busy) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                        Spacer(Modifier.size(8.dp))
                    }
                    Text(if (busy) "連接中…" else "連接並登錄")
                }

                Text(
                    "提示：PC 端設定需開啟「允許局域網訪問」",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}
