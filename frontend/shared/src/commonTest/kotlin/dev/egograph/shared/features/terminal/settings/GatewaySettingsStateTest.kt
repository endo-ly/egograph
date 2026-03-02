package dev.egograph.shared.features.terminal.settings

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * GatewaySettingsState のテスト
 *
 * GatewaySettingsState の初期状態、デフォルト値、派生プロパティを検証します。
 */
class GatewaySettingsStateTest {
    @Test
    fun `GatewaySettingsState starts with empty inputs`() {
        val state = GatewaySettingsState()

        assertEquals("", state.inputGatewayUrl)
    }

    @Test
    fun `GatewaySettingsState starts with isSaving false`() {
        val state = GatewaySettingsState()

        assertFalse(state.isSaving)
    }

    @Test
    fun `GatewaySettingsState canSave is false with empty inputs`() {
        val state = GatewaySettingsState()

        assertFalse(state.canSave)
    }

    @Test
    fun `GatewaySettingsState canSave is true with only URL`() {
        val state = GatewaySettingsState(inputGatewayUrl = "https://gateway.example.com")

        assertTrue(state.canSave)
    }

    @Test
    fun `GatewaySettingsState canSave is false with blank URL`() {
        val state = GatewaySettingsState(inputGatewayUrl = "   ")

        assertFalse(state.canSave)
    }

    @Test
    fun `GatewaySettingsState canSave is true with non-blank URL`() {
        val state = GatewaySettingsState(inputGatewayUrl = " https://gateway.example.com ")

        assertTrue(state.canSave)
    }

    @Test
    fun `GatewaySettingsState with custom values preserves values`() {
        val state =
            GatewaySettingsState(
                inputGatewayUrl = "https://gateway.example.com",
                isSaving = true,
            )

        assertEquals("https://gateway.example.com", state.inputGatewayUrl)
        assertEquals(true, state.isSaving)
    }
}
