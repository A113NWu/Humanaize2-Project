package com.humanaize.aizecompanion.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * 全局排版常量：頁面 16dp、卡片內 16dp、卡片間 12dp、圓角 16dp。
 */
object AizeLayout {
    val ScreenPadding = 16.dp
    val CardPadding = 16.dp
    val CardSpacing = 12.dp
    val ItemSpacing = 8.dp
    val CardCorner = 16.dp
}

/**
 * 頁面骨架：所有頁面統一的 Scaffold + TopAppBar，
 * 右上角固定展示頁面級狀態 chip。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AizePageScaffold(
    title: String,
    statusText: String? = null,
    statusColor: Color = MaterialTheme.colorScheme.onSurfaceVariant,
    actions: @Composable RowScope.() -> Unit = {},
    content: @Composable (PaddingValues) -> Unit
) {
    Scaffold(
        // 外層 MainTabs 已處理底部導航欄，這裡不再重複消費系統窗口邊距
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text(title, style = MaterialTheme.typography.titleLarge) },
                actions = {
                    if (statusText != null) {
                        StatusChip(
                            text = statusText,
                            color = statusColor,
                            modifier = Modifier.padding(end = 4.dp)
                        )
                    }
                    actions()
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface,
                    actionIconContentColor = MaterialTheme.colorScheme.onSurfaceVariant
                )
            )
        },
        content = content
    )
}

/** 彩色狀態點 + 一句話的 chip，替代整段紅字 */
@Composable
fun StatusChip(
    text: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(percent = 50),
        color = color.copy(alpha = 0.14f)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(color, CircleShape)
            )
            Text(
                text = text,
                style = MaterialTheme.typography.labelMedium,
                color = color
            )
        }
    }
}

/** 統一分組卡片：16dp 內邊距、16dp 圓角 */
@Composable
fun AizeCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(AizeLayout.CardCorner),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(
            modifier = Modifier.padding(AizeLayout.CardPadding),
            verticalArrangement = Arrangement.spacedBy(AizeLayout.ItemSpacing),
            content = content
        )
    }
}

/** 卡片內分組標題 */
@Composable
fun CardSectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleMedium,
        color = MaterialTheme.colorScheme.onSurface
    )
}

/**
 * 統一設置行：標題 + 副標題在左，控件固定最右。
 */
@Composable
fun SettingRow(
    title: String,
    subtitle: String? = null,
    control: @Composable () -> Unit = {}
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface
            )
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        Spacer(Modifier.width(12.dp))
        control()
    }
}

/** 內聯提示（錯誤/說明），替代大段裸文本 */
@Composable
fun InlineNotice(
    text: String,
    color: Color = MaterialTheme.colorScheme.error,
    icon: ImageVector? = null,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = color.copy(alpha = 0.10f)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            if (icon != null) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = color,
                    modifier = Modifier.size(18.dp)
                )
            }
            Text(
                text = text,
                style = MaterialTheme.typography.bodySmall,
                color = color
            )
        }
    }
}

/** 等寬代碼塊：診斷信息 / shell 輸出 */
@Composable
fun CodeBlock(
    text: String,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(12.dp),
            style = MaterialTheme.typography.bodySmall,
            fontFamily = FontFamily.Monospace,
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
