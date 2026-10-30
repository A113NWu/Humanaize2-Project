package com.humanaize.aizecompanion.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.humanaize.aizecompanion.R
import com.humanaize.aizecompanion.ui.MainActivity

/**
 * Aize 有新訊息時的系統通知。
 * 標題固定為「Aize」，正文為訊息內容（長訊息自動截斷）。
 */
object AizeNotifier {

    const val CHANNEL_ID = "aize_message_channel"

    @Volatile
    private var nextId = 1000

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Aize 訊息",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Aize 主動說話或回覆新訊息時提醒"
                setShowBadge(true)
            }
            context.getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
        }
    }

    fun notify(context: Context, text: String) {
        val body = text.trim()
        if (body.isEmpty()) return
        ensureChannel(context)

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Aize")
            .setContentText(body.take(120))
            .setStyle(NotificationCompat.BigTextStyle().bigText(body.take(500)))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        try {
            NotificationManagerCompat.from(context).notify(nextId++, notification)
        } catch (_: SecurityException) {
            // 用戶拒絕通知權限時靜默忽略
        }
    }
}
