package dev.egograph.shared.features.terminal.session.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import dev.egograph.shared.core.ui.common.testTagResourceId
import dev.egograph.shared.core.ui.theme.EgoGraphThemeTokens

private const val SPECIAL_KEY_COLUMNS = 6

private val SPECIAL_KEY_BUTTON_HEIGHT = 34.dp
private val SPECIAL_KEY_FONT_SIZE = 12.sp
private val SPECIAL_KEY_LINE_HEIGHT = 12.sp
private val SPECIAL_KEY_HORIZONTAL_PADDING = 2.dp
private val SPECIAL_KEY_ICON_SIZE = 16.dp

private data class TerminalPanelAction(
    val label: String,
    val keySequence: String? = null,
    val icon: ImageVector? = null,
    val isAccent: Boolean = false,
    val testTag: String? = null,
    val onClick: (() -> Unit)? = null,
)

/**
 * ターミナル用特殊キーパネル。
 *
 * 高さを抑えた 2 段レイアウトで、すべて同サイズのキーを並べる。
 *
 * @param onKeyPress キー送信コールバック
 * @param onVoiceInputClick 音声入力ボタン押下時のコールバック
 * @param isVoiceInputActive 音声入力が有効かどうか
 * @param modifier Modifier
 */
@Composable
fun SpecialKeysBar(
    onKeyPress: (String) -> Unit,
    onVoiceInputClick: () -> Unit,
    isVoiceInputActive: Boolean,
    modifier: Modifier = Modifier,
) {
    val dimens = EgoGraphThemeTokens.dimens
    val shapes = EgoGraphThemeTokens.shapes
    val actions =
        listOf(
            TerminalPanelAction(
                label = if (isVoiceInputActive) "Stop" else "Mic",
                icon = if (isVoiceInputActive) Icons.Filled.Stop else Icons.Filled.Mic,
                isAccent = isVoiceInputActive,
                testTag = "terminal_voice_button",
                onClick = onVoiceInputClick,
            ),
            TerminalPanelAction(label = "/", keySequence = "/"),
            TerminalPanelAction(label = "C-c", keySequence = "\u0003"),
            TerminalPanelAction(label = "C-d", keySequence = "\u0004"),
            TerminalPanelAction(label = "↑", keySequence = "\u001B[A"),
            TerminalPanelAction(label = "Esc", keySequence = "\u001B"),
            // 上下の境目
            TerminalPanelAction(label = "Tab", keySequence = "\t"),
            TerminalPanelAction(label = "S-Tab", keySequence = "\u001B[Z"),
            TerminalPanelAction(label = "←", keySequence = "\u001B[D"),
            TerminalPanelAction(label = "↓", keySequence = "\u001B[B"),
            TerminalPanelAction(label = "→", keySequence = "\u001B[C"),
        )

    Surface(
        modifier =
            modifier
                .testTagResourceId("special_keys_bar")
                .fillMaxWidth(),
        shape = shapes.radiusMd,
        color = MaterialTheme.colorScheme.surfaceContainerLow.copy(alpha = 0.98f),
        contentColor = MaterialTheme.colorScheme.onSurface,
        tonalElevation = dimens.zero,
        shadowElevation = dimens.zero,
        border =
            BorderStroke(
                width = dimens.borderWidthThin,
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.28f),
            ),
    ) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = dimens.space6, vertical = dimens.space6),
            verticalArrangement = Arrangement.spacedBy(dimens.space4),
        ) {
            actions.chunked(SPECIAL_KEY_COLUMNS).forEach { rowActions ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(dimens.space4),
                ) {
                    rowActions.forEach { action ->
                        SpecialPanelButton(
                            action = action,
                            onKeyPress = onKeyPress,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SpecialPanelButton(
    action: TerminalPanelAction,
    onKeyPress: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val shapes = EgoGraphThemeTokens.shapes
    val containerColor =
        if (action.isAccent) {
            MaterialTheme.colorScheme.errorContainer
        } else {
            MaterialTheme.colorScheme.surfaceVariant
        }
    val contentColor =
        if (action.isAccent) {
            MaterialTheme.colorScheme.onErrorContainer
        } else {
            MaterialTheme.colorScheme.onSurfaceVariant
        }

    Button(
        onClick = {
            action.onClick?.invoke() ?: action.keySequence?.let(onKeyPress)
        },
        modifier =
            modifier
                .then(
                    if (action.testTag != null) {
                        Modifier.testTagResourceId(action.testTag)
                    } else {
                        Modifier
                    },
                ).height(SPECIAL_KEY_BUTTON_HEIGHT),
        shape = shapes.radiusSm,
        colors =
            ButtonDefaults.buttonColors(
                containerColor = containerColor,
                contentColor = contentColor,
            ),
        contentPadding = PaddingValues(horizontal = SPECIAL_KEY_HORIZONTAL_PADDING, vertical = 0.dp),
    ) {
        if (action.icon != null) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    imageVector = action.icon,
                    contentDescription = action.label,
                    modifier = Modifier.size(SPECIAL_KEY_ICON_SIZE),
                )
            }
        } else {
            Text(
                text = action.label,
                style =
                    MaterialTheme.typography.labelSmall.copy(
                        fontSize = SPECIAL_KEY_FONT_SIZE,
                        lineHeight = SPECIAL_KEY_LINE_HEIGHT,
                    ),
                textAlign = TextAlign.Center,
                maxLines = 1,
            )
        }
    }
}
