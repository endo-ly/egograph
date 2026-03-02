package dev.egograph.android.fcm

import android.util.Log
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dev.egograph.android.notifications.NotificationChannelManager
import dev.egograph.android.notifications.NotificationDisplayer
import dev.egograph.shared.core.platform.PlatformPrefsKeys

/** Firebase Cloud Messaging サービス。

FCMトークンの更新とメッセージ受信を処理します。
*/
class FcmService : FirebaseMessagingService() {
    companion object {
        private const val TAG = "FcmService"
        private const val PREFS_NAME = "egograph_prefs"
        private const val KEY_GATEWAY_API_URL = "gateway_api_url"
        private const val TOKEN_PREVIEW_LENGTH = 10
    }

    private var tokenManager: FcmTokenManager? = null

    /** FCMトークンが更新されたときに呼ばれます。

     * @param token 新しいFCMトークン
     */
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "FCM token refreshed: ${token.take(TOKEN_PREVIEW_LENGTH)}...")

        getTokenManager()?.registerToken(
            token = token,
            deviceName = android.os.Build.MODEL,
        )
    }

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "FcmService.onCreate() called")

        // 通知チャンネルを作成（Android 8.0+）
        NotificationChannelManager.createNotificationChannel(this)
        Log.d(TAG, "Notification channel created")

        // 起動時に既存トークンの登録も試行

        // 起動時に既存トークンの登録も試行
        FirebaseMessaging
            .getInstance()
            .token
            .addOnSuccessListener { token ->
                if (!token.isNullOrBlank()) {
                    getTokenManager()?.registerToken(
                        token = token,
                        deviceName = android.os.Build.MODEL,
                    )
                }
            }.addOnFailureListener { error ->
                Log.w(TAG, "Failed to fetch initial FCM token: ${error.message}")
            }
    }

    private fun getTokenManager(): FcmTokenManager? {
        tokenManager?.let { return it }

        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val gatewayUrl = prefs.getString(KEY_GATEWAY_API_URL, "")?.trim().orEmpty()
        val apiKey =
            prefs
                .getString(PlatformPrefsKeys.KEY_API_KEY, "")
                ?.trim()
                .orEmpty()

        val manager: FcmTokenManager? =
            if (gatewayUrl.isBlank() || apiKey.isBlank()) {
                Log.w(TAG, "Skip FCM token registration: api_url or api_key is empty")
                null
            } else {
                FcmTokenManager(gatewayUrl = gatewayUrl, apiKey = apiKey)
            }

        manager?.let { tokenManager = it }
        return manager
    }

    override fun onDestroy() {
        tokenManager?.cleanup()
        tokenManager = null
        super.onDestroy()
    }

    /** FCMメッセージを受信したときに呼ばれます。

     * @param message 受信したRemoteMessage
     */
    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        Log.d(TAG, "Message received from: ${message.from}")

        // 通知ペイロードの処理
        message.notification?.let { notification ->
            // データペイロードに "task_completed" タイプが含まれる場合は、
            // そちらのデータペイロード処理で通知を表示するため、
            // notification タイプの通知をスキップして二重表示を防ぐ
            val hasTaskCompletedInData = message.data["type"] == "task_completed"
            if (!hasTaskCompletedInData) {
                Log.d(TAG, "Message Notification Body: ${notification.body}")
                // 通知を表示
                NotificationDisplayer.showNotification(
                    context = this,
                    title = notification.title ?: "EgoGraph",
                    message = notification.body ?: "New notification",
                )
            }
        }

        // データペイロードの処理
        if (message.data.isNotEmpty()) {
            Log.d(TAG, "Message data payload keys: ${message.data.keys}")

            val type = message.data["type"]

            when (type) {
                "task_completed" -> {
                    val sessionId = message.data["session_id"]
                    Log.d(TAG, "Task completed: $sessionId")
                    // データペイロードから通知を作成
                    NotificationDisplayer.showNotification(
                        context = this,
                        title = message.data["title"] ?: "Task Completed",
                        message = message.data["body"] ?: "Your task has been completed",
                    )
                }
            }
        }
    }
}
