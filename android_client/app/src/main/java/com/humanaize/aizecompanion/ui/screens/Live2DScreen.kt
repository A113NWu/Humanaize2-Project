package com.humanaize.aizecompanion.ui.screens

import android.annotation.SuppressLint
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel

/**
 * Live2D 頁：WebView 載入 PC 端的 Live2D 互動頁。
 * 動作/說話由後端 [motion:]/speak 命令推送，手機端純展示 + 可語音。
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun Live2DScreen(viewModel: MainViewModel) {
    val appSettings by viewModel.settings.collectAsState()
    val baseUrl = appSettings.baseUrl

    if (baseUrl.isEmpty()) {
        Column(
            modifier = Modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text("尚未配置服務器", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Text("請到「設定」頁填寫 PC 地址", style = MaterialTheme.typography.bodySmall)
        }
        return
    }

    // widget 模式：透明背景 + 去除頁面外框，適合嵌入手機界面
    val url = "$baseUrl/live2d?transparent=1&widget=1"
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { ctx ->
            WebView(ctx).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.mediaPlaybackRequiresUserGesture = false
                webViewClient = object : WebViewClient() {
                    override fun shouldOverrideUrlLoading(
                        view: WebView, request: WebResourceRequest
                    ): Boolean {
                        // 所有導航留在本 WebView（輪詢走 fetch，不觸發導航）
                        return false
                    }
                }
                loadUrl(url)
            }
        },
        update = { webView ->
            if (webView.url != url) webView.loadUrl(url)
        }
    )
}
