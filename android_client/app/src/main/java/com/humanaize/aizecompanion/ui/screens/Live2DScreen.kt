package com.humanaize.aizecompanion.ui.screens

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.graphics.Color as AndroidColor
import android.util.Log
import android.view.View
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.humanaize.aizecompanion.ui.components.AizePageScaffold
import com.humanaize.aizecompanion.ui.viewmodel.MainViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope

private const val TAG = "Live2D"

/**
 * Live2D 頁：WebView 全屏載入 PC 端的 Live2D 互動頁。
 * 動作/說話由後端 [motion:]/speak 命令推送，手機端純展示 + 可語音。
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun Live2DScreen(viewModel: MainViewModel) {
    val appSettings by viewModel.settings.collectAsState()
    val baseUrl = appSettings.baseUrl
    val scope = rememberCoroutineScope()

    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    var webViewRef by remember { mutableStateOf<WebView?>(null) }
    var loadedUrl by remember { mutableStateOf<String?>(null) }

    // 系統 WebView 被封裝/禁用時，任何 WebView 都只會白屏，先擋下來給明確提示
    val webViewPackage: String? = remember {
        try {
            WebView.getCurrentWebViewPackage()?.packageName
        } catch (t: Throwable) {
            Log.w(TAG, "WebView unavailable: ${t.message}")
            null
        }
    }

    val statusLabel = when {
        baseUrl.isEmpty() -> "未配置"
        webViewPackage == null -> "WebView 不可用"
        error != null -> "載入失敗"
        loading -> "載入中"
        else -> "已連接"
    }
    val statusColor = when {
        baseUrl.isEmpty() || error != null || webViewPackage == null ->
            MaterialTheme.colorScheme.error
        loading -> MaterialTheme.colorScheme.secondary
        else -> MaterialTheme.colorScheme.tertiary
    }

    AizePageScaffold(
        title = "Live2D",
        statusText = statusLabel,
        statusColor = statusColor
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
        ) {
            if (baseUrl.isEmpty()) {
                EmptyServerHint()
            } else if (webViewPackage == null) {
                ErrorOverlay(
                    message = "系統 WebView 不可用（可能被禁用或未安裝），\n請在應用商店更新「Android System WebView」或關閉對它的限制",
                    onRetry = { /* 無可重試：需用戶修復系統元件的話無法自動恢復 */ }
                )
            } else {
                val url = "$baseUrl/live2d?transparent=1&widget=1"
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { ctx ->
                        WebView(ctx).apply {
                            setBackgroundColor(AndroidColor.TRANSPARENT)
                            // 硬體層：Live2D 走 WebGL，軟體渲染會畫不出來（白屏）
                            setLayerType(View.LAYER_TYPE_HARDWARE, null)
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.mediaPlaybackRequiresUserGesture = false
                            settings.useWideViewPort = true
                            settings.loadWithOverviewMode = true
                            settings.mixedContentMode =
                                android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                            // 便於 adb chrome://inspect 遠端排查頁面問題
                            WebView.setWebContentsDebuggingEnabled(true)
                            webChromeClient = object : WebChromeClient() {
                                override fun onConsoleMessage(msg: ConsoleMessage): Boolean {
                                    val text = "${msg.message()} (${msg.sourceId()}:${msg.lineNumber()})"
                                    Log.i(TAG, "console: $text")
                                    if (msg.messageLevel() == ConsoleMessage.MessageLevel.ERROR) {
                                        notice = text
                                    }
                                    return true
                                }
                            }
                            webViewClient = object : WebViewClient() {
                                override fun shouldOverrideUrlLoading(
                                    view: WebView?,
                                    request: WebResourceRequest?
                                ): Boolean {
                                    // 所有導航留在本 WebView（輪詢走 fetch，不觸發導航）
                                    return false
                                }

                                override fun onPageStarted(
                                    view: WebView?,
                                    url: String?,
                                    favicon: Bitmap?
                                ) {
                                    loading = true
                                    error = null
                                    notice = null
                                }

                                override fun onPageFinished(view: WebView?, url: String?) {
                                    loading = false
                                    // 頁面載入完成後 8 秒仍沒有角色，多半是 WebGL/資源失敗
                                    scope.launch {
                                        delay(8000)
                                        val ok = try {
                                            val js = "(function(){return !!(window.PIXI && document.querySelector('#stage canvas'))})()"
                                            var alive = false
                                            view?.evaluateJavascript(js) { r -> alive = r == "true" }
                                            delay(600)
                                            alive
                                        } catch (t: Throwable) {
                                            false
                                        }
                                        if (!ok && loadedUrl == url) {
                                            notice = "頁面已載入但 Live2D 沒有渲染，可能是 WebView 的 WebGL 或模型資源載入失敗"
                                        }
                                    }
                                }

                                override fun onReceivedError(
                                    view: WebView?,
                                    request: WebResourceRequest?,
                                    errorResponse: WebResourceError?
                                ) {
                                    if (request?.isForMainFrame == true) {
                                        loading = false
                                        error = "無法連接 ${request.url.host}：" +
                                                (errorResponse?.description ?: "網絡錯誤")
                                    }
                                }
                            }
                            webViewRef = this
                            loadedUrl = url
                            loadUrl(url)
                        }
                    },
                    update = { webView ->
                        // 只在目標 URL 真的變了才重載，避免每次重組都 loadUrl 造成白屏閃爍
                        if (loadedUrl != url) {
                            loadedUrl = url
                            loading = true
                            error = null
                            notice = null
                            webView.loadUrl(url)
                        }
                    }
                )

                if (loading && error == null) {
                    LoadingOverlay()
                }

                error?.let { message ->
                    ErrorOverlay(
                        message = message,
                        onRetry = {
                            loading = true
                            error = null
                            notice = null
                            val wv = webViewRef
                            if (wv != null) wv.loadUrl(url) else loading = false
                        }
                    )
                }

                // 頁面腳本錯誤/渲染失敗：直接顯示出來，不再是一片空白
                notice?.let { text ->
                    Box(
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .padding(12.dp)
                            .background(
                                MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.92f),
                                MaterialTheme.shapes.small
                            )
                            .padding(10.dp)
                    ) {
                        Text(
                            text = text,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun LoadingOverlay() {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background.copy(alpha = 0.85f)),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(36.dp),
                strokeWidth = 3.dp
            )
            Text(
                "正在載入 Live2D…",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun ErrorOverlay(message: String, onRetry: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background.copy(alpha = 0.95f)),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier.padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Icon(
                Icons.Default.CloudOff,
                contentDescription = null,
                modifier = Modifier.size(40.dp),
                tint = MaterialTheme.colorScheme.error
            )
            Text(
                "Live2D 載入失敗",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                message,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
            Spacer(Modifier.height(4.dp))
            Button(onClick = onRetry) {
                Icon(
                    Icons.Default.Refresh,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(Modifier.width(6.dp))
                Text("重試")
            }
        }
    }
}

@Composable
private fun EmptyServerHint() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.CloudOff,
            contentDescription = null,
            modifier = Modifier.size(40.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(Modifier.height(12.dp))
        Text(
            "尚未配置服務器",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface
        )
        Spacer(Modifier.height(4.dp))
        Text(
            "請到「設定」頁填寫 PC 地址",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
