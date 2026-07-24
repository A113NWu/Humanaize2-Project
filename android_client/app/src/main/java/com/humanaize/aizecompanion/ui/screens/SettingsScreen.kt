package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.humanaize.aizecompanion.data.ContributionMode
import com.humanaize.aizecompanion.data.toContributionMode
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 设置页面
 * 
 * 配置服务器连接、设备信息和算力贡献参数。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(viewModel: MainViewModel) {
    val settings by viewModel.settings.collectAsState()
    
    var serverAddressInput by remember { mutableStateOf(settings.serverAddress) }
    var deviceNameInput by remember { mutableStateOf(settings.deviceName) }
    var maxTasksInput by remember { mutableStateOf(settings.maxConcurrentTasks.toString()) }
    var expandedModeMenu by remember { mutableStateOf(false) }
    
    // 当设置变化时同步输入框
    LaunchedEffect(settings) {
        serverAddressInput = settings.serverAddress
        deviceNameInput = settings.deviceName
        maxTasksInput = settings.maxConcurrentTasks.toString()
    }
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 服务器连接设置
        SectionHeader("服务器连接")
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedTextField(
                    value = serverAddressInput,
                    onValueChange = { serverAddressInput = it },
                    label = { Text("服务器地址") },
                    placeholder = { Text("ws://192.168.1.100:8765") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFFFF6B35)
                    )
                )
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = {
                            viewModel.updateServerAddress(serverAddressInput)
                        },
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFFFF6B35)
                        )
                    ) {
                        Icon(Icons.Default.Save, null)
                        Spacer(Modifier.width(4.dp))
                        Text("保存")
                    }
                    
                    OutlinedButton(
                        onClick = {
                            viewModel.connectToServer(serverAddressInput)
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.Refresh, null)
                        Spacer(Modifier.width(4.dp))
                        Text("重新连接")
                    }
                }
            }
        }
        
        // 设备设置
        SectionHeader("设备设置")
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedTextField(
                    value = deviceNameInput,
                    onValueChange = { 
                        deviceNameInput = it
                        viewModel.updateDeviceName(it)
                    },
                    label = { Text("设备名称") },
                    placeholder = { Text("我的手机") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFFFF6B35)
                    )
                )
                
                // 设备 ID（只读）
                if (settings.deviceId.isNotEmpty()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "设备 ID",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.Gray
                        )
                        Text(
                            text = settings.deviceId,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFFF6B35)
                        )
                    }
                }
            }
        }
        
        // 算力设置
        SectionHeader("算力设置")
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // 启用算力
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "启用算力贡献",
                            style = MaterialTheme.typography.bodyLarge
                        )
                        Text(
                            text = "将本机空闲算力用于分布式任务处理",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray
                        )
                    }
                    Switch(
                        checked = settings.enableCompute,
                        onCheckedChange = { viewModel.updateComputeEnabled(it) },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = Color.White,
                            checkedTrackColor = Color(0xFFFF6B35)
                        )
                    )
                }
                
                SimpleDivider()
                
                // 最大并发任务
                OutlinedTextField(
                    value = maxTasksInput,
                    onValueChange = { 
                        maxTasksInput = it.filter { c -> c.isDigit() }
                            .take(1)
                        viewModel.updateMaxConcurrentTasks(maxTasksInput.toIntOrNull() ?: 1)
                    },
                    label = { Text("最大并发任务数") },
                    modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFFFF6B35)
                    )
                )
                
                SimpleDivider()
                
                // 贡献模式
                ExposedDropdownMenuBox(
                    expanded = expandedModeMenu,
                    onExpandedChange = { expandedModeMenu = it }
                ) {
                    OutlinedTextField(
                        value = when (settings.contributionMode.toContributionMode()) {
                            ContributionMode.IDLE_ONLY -> "仅充电时"
                            ContributionMode.WIFI_ONLY -> "仅 WiFi 下"
                            ContributionMode.ALWAYS -> "始终"
                        },
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("贡献模式") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expandedModeMenu) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .menuAnchor(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color(0xFFFF6B35)
                        )
                    )
                    
                    ExposedDropdownMenu(
                        expanded = expandedModeMenu,
                        onDismissRequest = { expandedModeMenu = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text("仅充电时") },
                            onClick = {
                                viewModel.updateContributionMode("idle")
                                expandedModeMenu = false
                            }
                        )
                        DropdownMenuItem(
                            text = { Text("仅 WiFi 下") },
                            onClick = {
                                viewModel.updateContributionMode("wifi")
                                expandedModeMenu = false
                            }
                        )
                        DropdownMenuItem(
                            text = { Text("始终") },
                            onClick = {
                                viewModel.updateContributionMode("always")
                                expandedModeMenu = false
                            }
                        )
                    }
                }
            }
        }
        
        // 关于
        SectionHeader("关于")
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("版本", color = Color.Gray)
                    Text("1.0.0")
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("产品", color = Color.Gray)
                    Text("Aize Companion")
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("所属项目", color = Color.Gray)
                    Text("Humanaize 2.0 Agent")
                }
            }
        }
        
        // 退出按钮
        OutlinedButton(
            onClick = {
                viewModel.disconnect()
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(Icons.Default.Logout, null)
            Spacer(Modifier.width(4.dp))
            Text("断开连接")
        }
    }
}

@Composable
fun SectionHeader(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleMedium,
        fontWeight = FontWeight.Bold,
        color = Color(0xFFFF6B35)
    )
}

@Composable
fun SimpleDivider() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(1.dp)
            .background(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
    )
}
