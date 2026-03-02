package dev.egograph.shared.features.terminal.settings

import cafe.adriel.voyager.core.model.ScreenModel
import cafe.adriel.voyager.core.model.screenModelScope
import dev.egograph.shared.core.platform.PlatformPreferences
import dev.egograph.shared.core.platform.PlatformPrefsDefaults
import dev.egograph.shared.core.platform.PlatformPrefsKeys
import dev.egograph.shared.core.platform.getDefaultGatewayBaseUrl
import dev.egograph.shared.core.platform.isValidUrl
import dev.egograph.shared.core.platform.normalizeBaseUrl
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex

/**
 * Gateway設定画面のScreenModel
 *
 * Gateway接続情報（URL）の管理・保存・検証を行う。
 * 入力値の検証、正規化、永続化を担当し、UI StateとOne-shotイベントを管理する。
 *
 * @property preferences プラットフォーム設定ストア（URL永続化用）
 */

class GatewaySettingsScreenModel(
    private val preferences: PlatformPreferences,
) : ScreenModel {
    private val saveMutex = Mutex()

    private val _state = MutableStateFlow(GatewaySettingsState())
    val state: StateFlow<GatewaySettingsState> = _state.asStateFlow()

    private val _effect = Channel<GatewaySettingsEffect>(Channel.BUFFERED)
    val effect: Flow<GatewaySettingsEffect> = _effect.receiveAsFlow()

    init {
        _state.update {
            it.copy(
                inputGatewayUrl =
                    preferences
                        .getString(
                            PlatformPrefsKeys.KEY_GATEWAY_API_URL,
                            PlatformPrefsDefaults.DEFAULT_GATEWAY_API_URL,
                        ).ifBlank { getDefaultGatewayBaseUrl() },
            )
        }
    }

    fun onGatewayUrlChange(value: String) {
        _state.update { it.copy(inputGatewayUrl = value) }
    }

    fun saveSettings() {
        val current = _state.value
        if (current.isSaving) {
            return
        }

        val validationError =
            when {
                !isValidUrl(current.inputGatewayUrl) -> "有効なGateway URLを入力してください"
                else -> null
            }

        if (validationError != null) {
            screenModelScope.launch {
                _effect.send(GatewaySettingsEffect.ShowMessage(validationError))
            }
            return
        }

        screenModelScope.launch {
            if (!saveMutex.tryLock()) {
                return@launch
            }
            _state.update { it.copy(isSaving = true) }
            try {
                val normalizedGatewayUrl = normalizeBaseUrl(current.inputGatewayUrl)

                preferences.putString(PlatformPrefsKeys.KEY_GATEWAY_API_URL, normalizedGatewayUrl)

                _state.update {
                    it.copy(
                        inputGatewayUrl = normalizedGatewayUrl,
                    )
                }
                _effect.send(GatewaySettingsEffect.ShowMessage("Gateway settings saved"))
                _effect.send(GatewaySettingsEffect.NavigateBack)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _effect.send(GatewaySettingsEffect.ShowMessage("Failed to save settings: ${e.message}"))
            } finally {
                _state.update { it.copy(isSaving = false) }
                saveMutex.unlock()
            }
        }
    }
}
