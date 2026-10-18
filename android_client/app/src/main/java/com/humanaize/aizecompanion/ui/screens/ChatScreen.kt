package com.humanaize.aizecompanion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.humanaize.aizecompanion.ui.viewmodel.ChatItem
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 對話頁：與 PC 端 Aize 流式對話。
 * 思考/技能日誌幀渲染成小字彩色日誌行，與回覆正文分開。
 */
@Composable
fun ChatScreen(viewModel: MainViewModel) {
    val messages by viewModel.messages.collectAsState()
    val sending by viewModel.sending.collectAsState()
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }

    LaunchedEffect(messages.size, messages.lastOrNull()?.text) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    Column(modifier = Modifier.fillMaxSize().imePadding()) {
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(messages, key = { it.id }) { item ->
                when (item.role) {
                    ChatItem.Role.USER -> Bubble(text = item.text, isUser = true)
                    ChatItem.Role.ASSISTANT -> Bubble(text = item.text, isUser = false)
                    ChatItem.Role.LOG -> LogLine(kind = item.logKind ?: "thought", text = item.text)
                }
            }
            if (sending && messages.lastOrNull()?.role != ChatItem.Role.ASSISTANT) {
                item { Text("Aize 正在思考…", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp) }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                placeholder = { Text("輸入訊息…") },
                modifier = Modifier.weight(1f),
                maxLines = 4
            )
            IconButton(
                onClick = {
                    viewModel.sendChat(input)
                    input = ""
                },
                enabled = input.isNotBlank() && !sending
            ) {
                Icon(Icons.Default.Send, contentDescription = "發送",
                    tint = MaterialTheme.colorScheme.primary)
            }
            IconButton(onClick = { viewModel.clearChat() }) {
                Icon(Icons.Default.Delete, contentDescription = "清空",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun Bubble(text: String, isUser: Boolean) {
    val bg = if (isUser) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant
    val fg = if (isUser) Color.White else MaterialTheme.colorScheme.onSurface
    Box(
        modifier = Modifier.fillMaxWidth(),
        contentAlignment = if (isUser) Alignment.CenterEnd else Alignment.CenterStart
    ) {
        Box(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .background(bg, RoundedCornerShape(16.dp))
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            SelectionContainer {
                Text(text.ifEmpty { "…" }, color = fg, fontSize = 15.sp)
            }
        }
    }
}

/** 思考/技能日誌行：等寬字體 + 按類型著色，不混入對話氣泡 */
@Composable
private fun LogLine(kind: String, text: String) {
    val color = when (kind) {
        "skill" -> Color(0xFF00D4AA)
        "gan" -> Color(0xFF8A5BFF)
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
                    RoundedCornerShape(8.dp)
                )
                .padding(horizontal = 10.dp, vertical = 6.dp)
        )
    }
}
