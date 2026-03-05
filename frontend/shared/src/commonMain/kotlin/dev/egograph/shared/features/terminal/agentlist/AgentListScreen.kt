package dev.egograph.shared.features.terminal.agentlist

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import cafe.adriel.voyager.core.screen.Screen
import cafe.adriel.voyager.core.screen.ScreenKey
import cafe.adriel.voyager.core.screen.uniqueScreenKey
import cafe.adriel.voyager.koin.koinScreenModel
import dev.egograph.shared.features.terminal.agentlist.components.SessionList
import kotlinx.serialization.Transient

/**
 * エージェント（セッション）一覧画面
 *
 * Gatewayに接続されたターミナルセッション一覧を表示する。
 *
 * @param onSessionSelected セッション選択コールバック
 * @param onOpenGatewaySettings Gateway設定を開くコールバック
 * @param onShowError エラー表示コールバック
 */
class AgentListScreen(
    @Transient private val onSessionSelected: (String) -> Unit = {},
    @Transient private val onOpenGatewaySettings: () -> Unit = {},
    @Transient private val onShowError: (String) -> Unit = {},
) : Screen {
    override val key: ScreenKey = uniqueScreenKey

    @Composable
    override fun Content() {
        val screenModel = koinScreenModel<AgentListScreenModel>()
        val state by screenModel.state.collectAsState()

        LaunchedEffect(Unit) {
            screenModel.effect.collect { effect ->
                when (effect) {
                    is AgentListEffect.NavigateToSession -> {
                        onSessionSelected(effect.sessionId)
                    }
                    is AgentListEffect.ShowError -> {
                        onShowError(effect.message)
                    }
                }
            }
        }

        SessionList(
            sessions = state.sessions,
            isLoading = state.isLoadingSessions,
            error = state.sessionsError,
            onSessionClick = { sessionId ->
                screenModel.selectSession(sessionId)
            },
            onRefresh = {
                screenModel.loadSessions()
            },
            onOpenGatewaySettings = onOpenGatewaySettings,
            modifier = Modifier,
        )
    }
}
