package dev.egograph.shared.core.platform.terminal

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class CopyResultTest {
    @Test
    fun `CopyResult Success stores copied text`() {
        val result = CopyResult.Success("Terminal output line 1\nTerminal output line 2")

        assertIs<CopyResult.Success>(result)
        assertEquals("Terminal output line 1\nTerminal output line 2", result.text)
    }

    @Test
    fun `CopyResult Error stores error message`() {
        val result = CopyResult.Error("Terminal not initialized")

        assertIs<CopyResult.Error>(result)
        assertEquals("Terminal not initialized", result.message)
    }

    @Test
    fun `CopyResult supports empty payloads`() {
        val success = CopyResult.Success("")
        val error = CopyResult.Error("")

        assertEquals("", success.text)
        assertEquals("", error.message)
    }

    @Test
    fun `CopyResult variants remain distinguishable`() {
        val success: CopyResult = CopyResult.Success("text")
        val error: CopyResult = CopyResult.Error("error")

        assertEquals("text", assertIs<CopyResult.Success>(success).text)
        assertEquals("error", assertIs<CopyResult.Error>(error).message)
    }
}
