package com.humanaize.aizecompanion.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

/**
 * Aize 主題配置
 *
 * Android 12+ 使用 Material3 動態取色；低版本回退到 Aize 品牌橙色。
 * 頁面中所有顏色都應取自 MaterialTheme.colorScheme，避免深淺色失真。
 */
@Composable
fun AizeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit
) {
    val context = LocalContext.current
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> darkColorScheme(
            primary = Color(0xFFFF6B35),
            onPrimary = Color.White,
            primaryContainer = Color(0xFF4A1800),
            secondary = Color(0xFF8A5BFF),
            tertiary = Color(0xFF00D4AA),
            error = Color(0xFFFF5252),
            surface = Color(0xFF1A1A1A),
            background = Color(0xFF0F0F0F)
        )
        else -> lightColorScheme(
            primary = Color(0xFFFF6B35),
            onPrimary = Color.White,
            primaryContainer = Color(0xFFFFDBC5),
            secondary = Color(0xFF8A5BFF),
            tertiary = Color(0xFF00D4AA),
            error = Color(0xFFFF5252),
            surface = Color.White,
            background = Color(0xFFF5F5F5)
        )
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography(),
        content = content
    )
}
