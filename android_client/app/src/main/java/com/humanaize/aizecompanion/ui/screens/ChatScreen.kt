package com.humanaize.aizecompanion.ui.screens

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.Divider
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.humanaize.aizecompanion.ui.components.AizeLayout
import com.humanaize.aizecompanion.ui.components.AizePageScaffold
import com.humanaize.aizecompanion.ui.viewmodel.ChatItem
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 對話頁：與 PC 端 Aize 流式對話。
 * 氣泡左右分列並帶頭像/名字，時間戳弱化；思考/技能日誌幀渲染成獨立日誌行。
 */
@Composable
fun ChatScreen(viewModel: MainViewModel) {
    val messages by viewModel.messages.collectAsState()
    val sending by viewModel.sending.collectAsState()
    val settings by viewModel.settings.collectAsState()
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }

    LaunchedEffect(messages.size, messages.lastOrNull()?.text) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    val statusLabel = when {
        sending -> "正在輸入"
        settings.loggedIn -> "已連接"
        else -> "未連接"
    }
    val statusColor = when {
        sending -> MaterialTheme.colorScheme.tertiary
        settings.loggedIn -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.error
    }

    // 當前正在流式輸出的那條回覆
    val streamingId = if (sending) {
        messages.lastOrNull { it.role == ChatItem.Role.ASSISTANT }?.id
    } else null

    AizePageScaffold(
        title = "對話",
        statusText = statusLabel,
        statusColor = statusColor,
        actions = {
            if (messages.isNotEmpty()) {
                IconButton(onClick = { viewModel.clearChat() }) {
                    Icon(Icons.Default.Delete, contentDescription = "清空對話")
                }
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .imePadding()
        ) {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentPadding = PaddingValues(
                    horizontal = AizeLayout.ScreenPadding,
                    vertical = AizeLayout.CardSpacing
                ),
                verticalArrangement = Arrangement.spacedBy(AizeLayout.CardSpacing)
            ) {
                if (messages.isEmpty()) {
                    item {
                        EmptyChatHint()
                    }
                }
                items(messages, key = { it.id }) { item ->
                    when (item.role) {
                        ChatItem.Role.USER -> MessageRow(item = item, streaming = false)
                        ChatItem.Role.ASSISTANT -> {
                            if (item.id == streamingId && item.text.isEmpty()) {
                                TypingBubble()
                            } else {
                                MessageRow(
                                    item = item,
                                    streaming = item.id == streamingId && item.text.isNotEmpty()
                                )
                            }
                        }
                        ChatItem.Role.LOG -> LogLine(
                            kind = item.logKind ?: "thought",
                            text = item.text
                        )
                    }
                }
            }

            Divider(color = MaterialTheme.colorScheme.outlineVariant)

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = AizeLayout.ScreenPadding, vertical = AizeLayout.CardSpacing),
                verticalAlignment = Alignment.Bottom
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    placeholder = { Text("輸入訊息…") },
                    modifier = Modifier.weight(1f),
                    maxLines = 4,
                    shape = RoundedCornerShape(AizeLayout.CardCorner)
                )
                Spacer(Modifier.width(8.dp))
                FilledIconButton(
                    onClick = {
                        viewModel.sendChat(input)
                        input = ""
                    },
                    enabled = input.isNotBlank() && !sending,
                    modifier = Modifier.size(52.dp)
                ) {
                    Icon(Icons.Default.Send, contentDescription = "發送")
                }
            }
        }
    }
}

@Composable
private fun EmptyChatHint() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 64.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Icon(
            Icons.Default.ChatBubbleOutline,
            contentDescription = null,
            modifier = Modifier.size(40.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            "和 Aize 聊聊吧",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface
        )
        Text(
            "訊息會經 PC 端 Humanaize2 轉發給 Aize",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

/** 單條消息：頭像 + 名字 + 弱化時間戳 + 氣泡 */
@Composable
private fun MessageRow(item: ChatItem, streaming: Boolean) {
    val isUser = item.role == ChatItem.Role.USER
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
        verticalAlignment = Alignment.Top
    ) {
        if (!isUser) {
            Avatar(
                text = "A",
                container = MaterialTheme.colorScheme.secondaryContainer,
                content = MaterialTheme.colorScheme.onSecondaryContainer
            )
            Spacer(Modifier.width(8.dp))
        }

        Column(
            modifier = Modifier.widthIn(max = 280.dp),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = if (isUser) "你" else "Aize",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    text = formatTime(item.time),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
                )
            }
            Spacer(Modifier.height(4.dp))
            Surface(
                shape = RoundedCornerShape(AizeLayout.CardCorner),
                color = if (isUser) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.surfaceVariant
            ) {
                SelectionContainer {
                    Text(
                        text = item.text.ifEmpty { "…" },
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                        style = MaterialTheme.typography.bodyLarge,
                        color = if (isUser) MaterialTheme.colorScheme.onPrimary
                        else MaterialTheme.colorScheme.onSurface
                    )
                }
            }
            if (streaming) {
                Text(
                    text = "正在輸入…",
                    modifier = Modifier.padding(top = 4.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.tertiary
                )
            }
        }

        if (isUser) {
            Spacer(Modifier.width(8.dp))
            Avatar(
                text = "我",
                container = MaterialTheme.colorScheme.primary,
                content = MaterialTheme.colorScheme.onPrimary
            )
        }
    }
}

@Composable
private fun Avatar(text: String, container: Color, content: Color) {
    Box(
        modifier = Modifier
            .size(32.dp)
            .background(container, CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            color = content,
            maxLines = 1,
            overflow = TextOverflow.Clip
        )
    }
}

/** 等待首個 token 時的「正在輸入」氣泡 */
@Composable
private fun TypingBubble() {
    val transition = rememberInfiniteTransition(label = "typing")
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Bottom
    ) {
        Avatar(
            text = "A",
            container = MaterialTheme.colorScheme.secondaryContainer,
            content = MaterialTheme.colorScheme.onSecondaryContainer
        )
        Spacer(Modifier.width(8.dp))
        Surface(
            shape = RoundedCornerShape(AizeLayout.CardCorner),
            color = MaterialTheme.colorScheme.surfaceVariant
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 14.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(5.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                repeat(3) { index ->
                    val alpha by transition.animateFloat(
                        initialValue = 0.25f,
                        targetValue = 1f,
                        animationSpec = infiniteRepeatable(
                            animation = tween(durationMillis = 600, delayMillis = index * 150),
                            repeatMode = RepeatMode.Reverse
                        ),
                        label = "dot$index"
                    )
                    Box(
                        modifier = Modifier
                            .size(7.dp)
                            .background(
                                MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = alpha),
                                CircleShape
                            )
                    )
                }
            }
        }
    }
}

/** 思考/技能日誌行：等寬字體 + 按類型著色，不混入對話氣泡 */
@Composable
private fun LogLine(kind: String, text: String) {
    val color = when (kind) {
        "skill" -> MaterialTheme.colorScheme.tertiary
        "gan" -> MaterialTheme.colorScheme.secondary
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    SelectionContainer {
        Text(
            text = text,
            color = color,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f),
                    RoundedCornerShape(12.dp)
                )
                .padding(horizontal = 12.dp, vertical = 8.dp)
        )
    }
}

private fun formatTime(timeMs: Long): String =
    SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(timeMs))
