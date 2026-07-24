package com.humanaize.aizecompanion.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * Aize 主题配置
 * 
 * 使用橙色主色调，符合 Aize 品牌标识。
 */
@Composable
fun AizeTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) {
        darkColorScheme(
            primary = Color(0xFFFF6B35),
            onPrimary = Color.White,
            primaryContainer = Color(0xFF4A1800),
            secondary = Color(0xFF8A5BFF),
            tertiary = Color(0xFF00D4AA),
            error = Color(0xFFFF5252),
            surface = Color(0xFF1A1A1A),
            background = Color(0xFF0F0F0F)
        )
    } else {
        lightColorScheme(
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
