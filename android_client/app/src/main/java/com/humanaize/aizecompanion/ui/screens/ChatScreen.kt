package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.humanaize.aizecompanion.data.ChatMessage
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 聊天页面
 * 
 * 与 Aize 对话的主界面，支持流式响应显示。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(viewModel: MainViewModel) {
    val messages by viewModel.chatMessages.collectAsState()
    val streamingMessage by viewModel.streamingMessage.collectAsState()
    val isLoading by viewModel.chatLoading.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()
    
    var inputText by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    val listState = rememberLazyListState()
    
    // 自动滚动到最新消息
    LaunchedEffect(messages.size, streamingMessage) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size)
        }
    }
    
    Column(
        modifier = Modifier.fillMaxSize()
    ) {
        // 连接状态提示
        if (connectionState != "connected") {
            ConnectionWarningBar(connectionState)
        }
        
        // 消息列表
        LazyColumn(
            state = listState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 12.dp)
        ) {
            if (messages.isEmpty() && streamingMessage == null) {
                item {
                    EmptyChatHint()
                }
            } else {
                items(messages) { message ->
                    ChatMessageBubble(message)
                }
                
                // 显示流式消息
                streamingMessage?.let { message ->
                    item {
                        ChatMessageBubble(message)
                    }
                }
            }
        }
        
        // 输入区域
        InputBar(
            text = inputText,
            onTextChange = { inputText = it },
            onSend = {
                if (inputText.isNotBlank()) {
                    viewModel.sendChatMessage(inputText)
                    inputText = ""
                    focusManager.clearFocus()
                }
            },
            isLoading = isLoading,
            isConnected = connectionState == "connected",
            onClearHistory = { viewModel.clearChatHistory() }
        )
    }
}

@Composable
fun ConnectionWarningBar(state: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFFFFEB3B).copy(alpha = 0.2f))
            .padding(8.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Icon(
                Icons.Default.Warning,
                contentDescription = null,
                tint = Color(0xFFFF9800),
                modifier = Modifier.size(20.dp)
            )
            Text(
                text = when (state) {
                    "connecting" -> "正在连接服务器..."
                    else -> "未连接到服务器，消息将无法发送"
                },
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFFE65100)
            )
        }
    }
}

@Composable
fun EmptyChatHint() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                Icons.Default.SmartToy,
                contentDescription = null,
                tint = Color(0xFFFF6B35),
                modifier = Modifier.size(64.dp)
            )
            Text(
                text = "与 Aize 开始对话",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "连接服务器后，即可在这里与 Aize 进行智能对话",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.Gray
            )
        }
    }
}

@Composable
fun ChatMessageBubble(message: ChatMessage) {
    val isUser = message.role == "user"
    
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        if (!isUser) {
            // AI 头像
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(Color(0xFFFF6B35)),
                contentAlignment = Alignment.Center
            ) {
                Text("A", color = Color.White, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.width(8.dp))
        }
        
        Column(
            modifier = Modifier.widthIn(max = 280.dp)
        ) {
            // 发送者名称
            Text(
                text = if (isUser) "我" else "Aize",
                style = MaterialTheme.typography.labelSmall,
                color = Color.Gray,
                modifier = Modifier.padding(horizontal = 4.dp)
            )
            
            // 消息气泡
            Box(
                modifier = Modifier
                    .clip(
                        RoundedCornerShape(
                            topStart = 16.dp,
                            topEnd = 16.dp,
                            bottomStart = if (isUser) 16.dp else 4.dp,
                            bottomEnd = if (isUser) 4.dp else 16.dp
                        )
                    )
                    .background(
                        if (isUser) Color(0xFFFF6B35) else Color(0xFFF5F5F5)
                    )
                    .padding(12.dp)
            ) {
                Text(
                    text = message.content,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (isUser) Color.White else Color.Black
                )
                
                // 流式指示器
                if (message.isStreaming) {
                    Spacer(Modifier.height(4.dp))
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(2.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(Color.Gray)
                        )
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(Color.Gray)
                        )
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(Color.Gray)
                        )
                    }
                }
            }
        }
        
        if (isUser) {
            Spacer(Modifier.width(8.dp))
            // 用户头像
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(Color(0xFF2196F3)),
                contentAlignment = Alignment.Center
            ) {
                Text("我", color = Color.White, fontSize = 12.sp)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InputBar(
    text: String,
    onTextChange: (String) -> Unit,
    onSend: () -> Unit,
    isLoading: Boolean,
    isConnected: Boolean,
    onClearHistory: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .padding(8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // 清除历史按钮
            IconButton(onClick = onClearHistory) {
                Icon(
                    Icons.Default.DeleteSweep,
                    contentDescription = "Clear",
                    tint = Color.Gray
                )
            }
            
            // 输入框
            OutlinedTextField(
                value = text,
                onValueChange = onTextChange,
                placeholder = { Text("输入消息...") },
                modifier = Modifier.weight(1f),
                enabled = !isLoading && isConnected,
                maxLines = 3,
                shape = RoundedCornerShape(24.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color(0xFFFF6B35),
                    unfocusedBorderColor = Color.Gray
                )
            )
            
            // 发送按钮
            IconButton(
                onClick = onSend,
                enabled = text.isNotBlank() && !isLoading && isConnected,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(
                        if (text.isNotBlank() && !isLoading && isConnected) 
                            Color(0xFFFF6B35) else Color.Gray.copy(alpha = 0.3f)
                    )
            ) {
                Icon(
                    Icons.Default.Send,
                    contentDescription = "Send",
                    tint = Color.White
                )
            }
        }
        
        // 加载状态提示
        if (isLoading) {
            Text(
                text = "Aize 正在思考...",
                style = MaterialTheme.typography.labelSmall,
                color = Color.Gray,
                modifier = Modifier.padding(start = 48.dp, top = 4.dp)
            )
        }
    }
}

private fun formatTime(timestamp: Double): String {
    val s = timestamp.toLong() / 1000
    val h = (s / 3600) % 24
    val m = (s / 60) % 60
    return String.format("%02d:%02d", h, m)
}
