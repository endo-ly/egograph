package dev.egograph.shared.core.domain.model.terminal

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * ターミナル snapshot モデル
 *
 * Copy mode 用に取得したプレーンテキストを表現します。
 *
 * @property sessionId セッション一意識別子
 * @property content キャプチャしたテキスト
 */
@Serializable
data class TerminalSnapshot(
    @SerialName("session_id")
    val sessionId: String,
    @SerialName("content")
    val content: String,
)
