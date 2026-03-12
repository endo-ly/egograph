package dev.egograph.shared.core.domain.model.terminal

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Terminal Session モデル
 *
 * ターミナルセッションの情報を表現します。
 *
 * @property sessionId セッション一意識別子
 * @property name セッション名
 * @property status セッション状態
 * @property lastActivity 最終アクティビティ日時 (ISO 8601形式)
 * @property createdAt 作成日時 (ISO 8601形式)
 */
@Serializable
data class Session(
    @SerialName("session_id")
    val sessionId: String,
    @SerialName("name")
    val name: String,
    @SerialName("status")
    val status: SessionStatus,
    @SerialName("last_activity")
    val lastActivity: String,
    @SerialName("created_at")
    val createdAt: String,
    @SerialName("preview_available")
    val previewAvailable: Boolean = false,
    @SerialName("preview_lines")
    val previewLines: List<String> = emptyList(),
)

/**
 * セッション状態
 */
@Serializable
enum class SessionStatus {
    /** 接続中 */
    @SerialName("connected")
    CONNECTED,
}
