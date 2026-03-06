package dev.egograph.shared.features.terminal.agentlist

import dev.egograph.shared.core.domain.model.terminal.Session

/**
 * ターミナル画面の状態
 *
 * @property sessions セッション一覧
 * @property isLoadingSessions セッション一覧読み込み中
 * @property sessionsError セッション関連のエラーメッセージ
 */
data class AgentListState(
    val sessions: List<Session> = emptyList(),
    val isLoadingSessions: Boolean = false,
    val sessionsError: String? = null,
)
