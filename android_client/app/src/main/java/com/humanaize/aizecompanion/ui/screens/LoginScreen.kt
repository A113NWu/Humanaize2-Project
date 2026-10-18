package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
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

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            "連接到你的 Aize",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(Modifier.height(8.dp))
        Text(
            "填 PC 端 Humanaize2 的局域網地址與 Web 賬號",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(24.dp))

        OutlinedTextField(
            value = server,
            onValueChange = { server = it },
            label = { Text("服務器地址") },
            placeholder = { Text("192.168.1.10:8082") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text("賬號") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("密碼") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(20.dp))

        Button(
            onClick = { viewModel.login(server, username, password) },
            enabled = loginState !is MainViewModel.LoginState.Busy && server.isNotBlank(),
            modifier = Modifier.fillMaxWidth()
        ) {
            if (loginState is MainViewModel.LoginState.Busy) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .height(18.dp)
                        .padding(end = 8.dp),
                    strokeWidth = 2.dp
                )
            }
            Text("連接並登錄")
        }

        when (val st = loginState) {
            is MainViewModel.LoginState.Fail -> {
                Spacer(Modifier.height(12.dp))
                Text(st.message, color = MaterialTheme.colorScheme.error)
            }
            else -> Unit
        }

        Spacer(Modifier.height(24.dp))
        Text(
            "提示：PC 端設定需開啟「允許局域網訪問」",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
