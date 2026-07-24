package com.humanaize.aizecompanion.ui.screens

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.humanaize.aizecompanion.R
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 首页
 * 
 * 显示连接状态、设备信息和快速操作入口。
 */
@Composable
fun HomeScreen(viewModel: MainViewModel) {
    val connectionState by viewModel.connectionState.collectAsState()
    val settings by viewModel.settings.collectAsState()
    val stats by viewModel.computeStats.collectAsState()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 连接状态卡片
        ConnectionCard(
            state = connectionState,
            serverAddress = settings.serverAddress,
            deviceName = settings.deviceName,
            onConnect = { viewModel.connectToServer(settings.serverAddress) },
            onDisconnect = { viewModel.disconnect() }
        )
        
        // 设备信息
        DeviceInfoCard(
            deviceName = settings.deviceName,
            deviceId = settings.deviceId.ifEmpty { "未注册" },
            totalTasks = stats.totalTasksCompleted,
            computeTime = formatDuration(stats.totalComputeTimeMs)
        )
        
        // 快捷操作
        QuickActionsRow(
            onStartCompute = { viewModel.updateComputeEnabled(true) },
            onStopCompute = { viewModel.updateComputeEnabled(false) }
        )
    }
}

@Composable
fun ConnectionCard(
    state: String,
    serverAddress: String,
    deviceName: String,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit
) {
    val statusColor by animateColorAsState(
        targetValue = when (state) {
            "connected" -> Color(0xFF4CAF50)
            "connecting" -> Color(0xFFFFB300)
            else -> Color.Gray
        }
    )
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // 状态指示器
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .clip(CircleShape)
                        .background(statusColor)
                )
                
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = when (state) {
                            "connected" -> stringResource(R.string.status_connected)
                            "connecting" -> stringResource(R.string.status_connecting)
                            else -> stringResource(R.string.status_disconnected)
                        },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = serverAddress,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray,
                        maxLines = 1
                    )
                }
                
                // 操作按钮
                if (state == "connected") {
                    OutlinedButton(onClick = onDisconnect) {
                        Text("断开")
                    }
                } else {
                    Button(
                        onClick = onConnect,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFFFF6B35)
                        )
                    ) {
                        Text("连接")
                    }
                }
            }
        }
    }
}

@Composable
fun DeviceInfoCard(
    deviceName: String,
    deviceId: String,
    totalTasks: Int,
    computeTime: String
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "设备信息",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            
            InfoRow(label = "设备名称", value = deviceName)
            InfoRow(label = "设备 ID", value = deviceId)
            InfoRow(label = "已完成任务", value = totalTasks.toString())
            InfoRow(label = "算力贡献", value = computeTime)
        }
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = Color.Gray
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

@Composable
fun QuickActionsRow(
    onStartCompute: () -> Unit,
    onStopCompute: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        OutlinedButton(
            onClick = onStartCompute,
            modifier = Modifier.weight(1f)
        ) {
            Icon(Icons.Default.Bolt, "Start")
            Spacer(Modifier.width(4.dp))
            Text("启动算力")
        }
        
        OutlinedButton(
            onClick = onStopCompute,
            modifier = Modifier.weight(1f)
        ) {
            Icon(Icons.Default.PowerSettingsNew, "Stop")
            Spacer(Modifier.width(4.dp))
            Text("停止算力")
        }
    }
}

private fun formatDuration(ms: Long): String {
    val seconds = ms / 1000
    val minutes = seconds / 60
    val hours = minutes / 60
    
    return when {
        hours > 0 -> "${hours}h ${minutes % 60}m"
        minutes > 0 -> "${minutes}m ${seconds % 60}s"
        else -> "${seconds}s"
    }
}
