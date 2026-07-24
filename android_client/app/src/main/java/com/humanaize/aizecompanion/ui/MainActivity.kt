package com.humanaize.aizecompanion.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.humanaize.aizecompanion.AizeApplication
import com.humanaize.aizecompanion.R
import com.humanaize.aizecompanion.ui.screens.ChatScreen
import com.humanaize.aizecompanion.ui.screens.ComputeScreen
import com.humanaize.aizecompanion.ui.screens.HomeScreen
import com.humanaize.aizecompanion.ui.screens.SettingsScreen
import com.humanaize.aizecompanion.ui.theme.AizeTheme
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 主 Activity
 * 
 * 使用 Jetpack Compose 构建现代 UI，
 * 包含底部导航栏和四个主要功能页面。
 */
class MainActivity : ComponentActivity() {
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val app = application as AizeApplication
        
        setContent {
            AizeTheme {
                MainScreen(app)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(app: AizeApplication) {
    val viewModel: MainViewModel = viewModel()
    var selectedTab by remember { mutableIntStateOf(0) }
    
    val tabs = listOf(
        stringResource(R.string.nav_home),
        stringResource(R.string.nav_compute),
        stringResource(R.string.nav_chat),
        stringResource(R.string.nav_settings)
    )
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Aize Companion",
                        color = Color.White
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFFFF6B35)
                ),
                actions = {
                    // 连接状态指示器
                    val connectionState by viewModel.connectionState.collectAsState()
                    ConnectionStatusIcon(connectionState)
                }
            )
        },
        bottomBar = {
            NavigationBar(
                containerColor = MaterialTheme.colorScheme.surface
            ) {
                tabs.forEachIndexed { index, title ->
                    NavigationBarItem(
                        icon = {
                            Icon(
                                imageVector = when (index) {
                                    0 -> Icons.Default.Home
                                    1 -> Icons.Default.Bolt
                                    2 -> Icons.Default.Chat
                                    3 -> Icons.Default.Settings
                                    else -> Icons.Default.Home
                                },
                                contentDescription = title
                            )
                        },
                        label = { Text(title) },
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Color(0xFFFF6B35),
                            selectedTextColor = Color(0xFFFF6B35)
                        )
                    )
                }
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier.padding(paddingValues)
        ) {
            when (selectedTab) {
                0 -> HomeScreen(viewModel)
                1 -> ComputeScreen(viewModel)
                2 -> ChatScreen(viewModel)
                3 -> SettingsScreen(viewModel)
            }
        }
    }
}

@Composable
fun ConnectionStatusIcon(state: String) {
    val color = when (state) {
        "connected" -> Color(0xFF4CAF50)
        "connecting" -> Color(0xFFFFB300)
        else -> Color.Gray
    }
    
    Icon(
        imageVector = when (state) {
            "connected" -> Icons.Default.Wifi
            "connecting" -> Icons.Default.WifiTethering
            else -> Icons.Default.WifiOff
        },
        contentDescription = state,
        tint = color,
        modifier = Modifier.size(24.dp)
    )
}
