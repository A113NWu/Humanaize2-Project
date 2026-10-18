package com.humanaize.aizecompanion.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.humanaize.aizecompanion.R
import com.humanaize.aizecompanion.ui.screens.ChatScreen
import com.humanaize.aizecompanion.ui.screens.Live2DScreen
import com.humanaize.aizecompanion.ui.screens.LoginScreen
import com.humanaize.aizecompanion.ui.screens.SettingsScreen
import com.humanaize.aizecompanion.ui.screens.ShizukuScreen
import com.humanaize.aizecompanion.ui.theme.AizeTheme
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * 主 Activity：未登錄顯示登錄頁；已連接顯示四個分頁
 * （對話 / Live2D / Shizuku / 設定），全部 Material3。
 */
class MainActivity : ComponentActivity() {

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { _ -> }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        setContent {
            AizeTheme {
                val viewModel: MainViewModel = viewModel()
                val settings by viewModel.settings.collectAsState()
                if (settings.baseUrl.isEmpty() || !settings.loggedIn) {
                    LoginScreen(viewModel)
                } else {
                    MainTabs(viewModel)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainTabs(viewModel: MainViewModel) {
    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf(
        stringResource(R.string.nav_chat),
        stringResource(R.string.nav_live2d),
        stringResource(R.string.nav_shizuku),
        stringResource(R.string.nav_settings)
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Aize Companion", color = Color.White) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary
                ),
                actions = { ConnectionDot(viewModel) }
            )
        },
        bottomBar = {
            NavigationBar {
                tabs.forEachIndexed { index, title ->
                    NavigationBarItem(
                        icon = {
                            Icon(
                                imageVector = when (index) {
                                    0 -> Icons.Default.Chat
                                    1 -> Icons.Default.Face
                                    2 -> Icons.Default.Terminal
                                    else -> Icons.Default.Settings
                                },
                                contentDescription = title
                            )
                        },
                        label = { Text(title) },
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.primary,
                            selectedTextColor = MaterialTheme.colorScheme.primary
                        )
                    )
                }
            }
        }
    ) { paddingValues ->
        Box(modifier = Modifier.padding(paddingValues)) {
            when (selectedTab) {
                0 -> ChatScreen(viewModel)
                1 -> Live2DScreen(viewModel)
                2 -> ShizukuScreen(viewModel)
                3 -> SettingsScreen(viewModel)
            }
        }
    }
}

/** 頂欄連接指示：服務器可達性（進入頁面即已登錄，僅作提示） */
@Composable
private fun ConnectionDot(viewModel: MainViewModel) {
    val settings by viewModel.settings.collectAsState()
    Icon(
        imageVector = if (settings.loggedIn) Icons.Default.Wifi else Icons.Default.WifiOff,
        contentDescription = null,
        tint = if (settings.loggedIn) Color(0xFF7CFC98) else Color.Gray,
        modifier = Modifier.size(22.dp)
    )
}
