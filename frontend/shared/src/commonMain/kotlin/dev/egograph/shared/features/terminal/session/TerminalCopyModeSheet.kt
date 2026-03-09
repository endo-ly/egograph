package dev.egograph.shared.features.terminal.session

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import dev.egograph.shared.core.domain.model.terminal.TerminalSnapshot
import dev.egograph.shared.core.domain.repository.TerminalRepository
import dev.egograph.shared.core.ui.components.ErrorView
import dev.egograph.shared.core.ui.components.LoadingView
import dev.egograph.shared.core.ui.theme.EgoGraphThemeTokens
import dev.egograph.shared.core.ui.theme.monospaceBody
import org.koin.compose.koinInject

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TerminalCopyModeSheet(
    agentId: String,
    onDismiss: () -> Unit,
) {
    val repository = koinInject<TerminalRepository>()
    val dimens = EgoGraphThemeTokens.dimens
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    var reloadToken by remember(agentId) { mutableStateOf(0) }
    var activeRequestId by remember(agentId) { mutableStateOf(0) }
    var snapshot by remember(agentId) { mutableStateOf<TerminalSnapshot?>(null) }
    var isLoading by remember(agentId) { mutableStateOf(true) }
    var error by remember(agentId) { mutableStateOf<String?>(null) }

    suspend fun loadSnapshot(requestId: Int) {
        isLoading = true
        error = null
        repository
            .getSnapshot(agentId)
            .onSuccess {
                if (activeRequestId != requestId) {
                    return@onSuccess
                }
                snapshot = it
            }.onFailure {
                if (activeRequestId != requestId) {
                    return@onFailure
                }
                snapshot = null
                error = it.message ?: "Failed to load terminal snapshot"
            }
        if (activeRequestId != requestId) {
            return
        }
        isLoading = false
    }

    LaunchedEffect(agentId, reloadToken) {
        val requestId = activeRequestId + 1
        activeRequestId = requestId
        loadSnapshot(requestId)
    }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .fillMaxHeight(0.9f)
                    .padding(horizontal = dimens.space16),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = "Copy Mode",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Button(
                    onClick = { reloadToken += 1 },
                ) {
                    Text("Refresh")
                }
            }

            Spacer(modifier = Modifier.height(dimens.space8))

            Text(
                text = "Long press and drag to select terminal text",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(modifier = Modifier.height(dimens.space12))

            when {
                isLoading -> {
                    LoadingView(
                        modifier = Modifier.fillMaxWidth(),
                        message = "Loading terminal text...",
                    )
                }

                error != null -> {
                    ErrorView(message = error ?: "Unknown error")
                    Spacer(modifier = Modifier.height(dimens.space12))
                    Button(
                        onClick = { reloadToken += 1 },
                    ) {
                        Text("Retry")
                    }
                }

                else -> {
                    val verticalScroll = rememberScrollState()
                    val horizontalScroll = rememberScrollState()
                    LaunchedEffect(snapshot?.content) {
                        withFrameNanos { }
                        withFrameNanos { }
                        verticalScroll.scrollTo(verticalScroll.maxValue)
                    }
                    SelectionContainer {
                        Text(
                            text =
                                snapshot?.content?.ifBlank { "No terminal output available." }
                                    ?: "No terminal output available.",
                            style = MaterialTheme.typography.monospaceBody,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier =
                                Modifier
                                    .fillMaxWidth()
                                    .weight(1f)
                                    .background(MaterialTheme.colorScheme.surfaceContainerLow)
                                    .padding(dimens.space16)
                                    .verticalScroll(verticalScroll)
                                    .horizontalScroll(horizontalScroll),
                            softWrap = false,
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(dimens.space16))
        }
    }
}
