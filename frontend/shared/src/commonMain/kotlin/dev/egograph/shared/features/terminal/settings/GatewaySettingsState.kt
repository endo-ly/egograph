package dev.egograph.shared.features.terminal.settings

/**
 * Gateway設定画面のUI状態
 *
 * @property inputGatewayUrl 入力されたGateway URL
 * @property isSaving 保存処理中かどうか
 */

data class GatewaySettingsState(
    val inputGatewayUrl: String = "",
    val isSaving: Boolean = false,
) {
    val canSave: Boolean
        get() = inputGatewayUrl.isNotBlank()
}
