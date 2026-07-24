package com.humanaize.aizecompanion.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.humanaize.aizecompanion.compute.CompletedTask
import com.humanaize.aizecompanion.data.ComputeStats
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 算力页面
 * 
 * 显示算力贡献统计、当前任务状态和历史记录。
 */
@Composable
fun ComputeScreen(viewModel: MainViewModel) {
    val stats by viewModel.computeStats.collectAsState()
    val completedTasks by viewModel.completedTasks.collectAsState()
    val settings by viewModel.settings.collectAsState()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 算力开关
        ComputeToggle(
            enabled = settings.enableCompute,
            onToggle = { viewModel.updateComputeEnabled(it) }
        )
        
        // 当前任务
        if (stats.isComputing) {
            CurrentTaskCard(stats)
        }
        
        // 统计卡片
        StatsCards(stats)
        
        // 任务历史
        if (completedTasks.isNotEmpty()) {
            TaskHistoryList(completedTasks.take(10))
        } else {
            EmptyHistoryHint()
        }
        
        // 重置按钮
        if (stats.totalTasksCompleted > 0) {
            OutlinedButton(
                onClick = { viewModel.resetComputeStats() },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.Refresh, "Reset")
                Spacer(Modifier.width(4.dp))
                Text("重置统计")
            }
        }
    }
}

@Composable
fun ComputeToggle(
    enabled: Boolean,
    onToggle: (Boolean) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Icon(
                    Icons.Default.Bolt,
                    contentDescription = null,
                    tint = Color(0xFFFF6B35),
                    modifier = Modifier.size(32.dp)
                )
                Column {
                    Text(
                        text = "算力贡献",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = if (enabled) "正在贡献算力" else "已暂停",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray
                    )
                }
            }
            
            Switch(
                checked = enabled,
                onCheckedChange = onToggle,
                colors = SwitchDefaults.colors(
                    checkedThumbColor = Color.White,
                    checkedTrackColor = Color(0xFFFF6B35)
                )
            )
        }
    }
}

@Composable
fun CurrentTaskCard(stats: ComputeStats) {
    val progress by animateFloatAsState(
        targetValue = stats.currentTaskProgress,
        label = "progress"
    )
    
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFFFFF3E0)
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    Icons.Default.AutoAwesome,
                    contentDescription = null,
                    tint = Color(0xFFFF6B35)
                )
                Text(
                    text = "正在处理任务",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            
            Text(
                text = stats.currentTaskId ?: "Unknown",
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray
            )
            
            LinearProgressIndicator(
                progress = progress,
                modifier = Modifier.fillMaxWidth(),
                color = Color(0xFFFF6B35),
                trackColor = Color(0xFFFFE0B2),
                strokeCap = StrokeCap.Round
            )
        }
    }
}

@Composable
fun StatsCards(stats: ComputeStats) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        StatCard(
            title = "总任务",
            value = stats.totalTasksCompleted.toString(),
            icon = Icons.Default.Assignment,
            modifier = Modifier.weight(1f)
        )
        StatCard(
            title = "算力时间",
            value = formatMs(stats.totalComputeTimeMs),
            icon = Icons.Default.Timer,
            modifier = Modifier.weight(1f)
        )
        StatCard(
            title = "效率",
            value = String.format("%.1f/m", stats.tasksPerMinute),
            icon = Icons.Default.Speed,
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
fun StatCard(
    title: String,
    value: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = Color(0xFFFF6B35),
                modifier = Modifier.size(24.dp)
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = title,
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray
            )
        }
    }
}

@Composable
fun TaskHistoryList(tasks: List<CompletedTask>) {
    Column(
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = "最近任务",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        
        LazyColumn(
            modifier = Modifier.height(200.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            items(tasks.size) { index ->
                val task = tasks[index]
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = if (task.success) Icons.Default.CheckCircle else Icons.Default.Error,
                            contentDescription = null,
                            tint = if (task.success) Color(0xFF4CAF50) else Color(0xFFFF5252),
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(Modifier.width(8.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = task.taskId.take(8) + "...",
                                style = MaterialTheme.typography.bodySmall
                            )
                            Text(
                                text = if (task.success) "完成" else "失败",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (task.success) Color(0xFF4CAF50) else Color(0xFFFF5252)
                            )
                        }
                        Text(
                            text = formatTime(task.completedAt),
                            style = MaterialTheme.typography.labelSmall,
                            color = Color.Gray
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun EmptyHistoryHint() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                Icons.Default.Inbox,
                contentDescription = null,
                tint = Color.Gray,
                modifier = Modifier.size(48.dp)
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "暂无任务记录",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.Gray
            )
        }
    }
}

private fun formatMs(ms: Long): String {
    val seconds = ms / 1000
    val minutes = seconds / 60
    return if (minutes > 0) "${minutes}m" else "${seconds}s"
}

private fun formatTime(timestamp: Long): String {
    val date = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.getDefault())
    return date.format(java.util.Date(timestamp))
}
