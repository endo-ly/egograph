package dev.egograph.shared.core.platform.terminal

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

class AndroidTerminalWebViewTest {
    @Test
    fun `createTerminalWebView without Context is unsupported on Android`() {
        assertFailsWith<NotImplementedError> {
            createTerminalWebView()
        }
    }

    @Test
    fun `toCopyResult copies visible terminal text on success`() {
        var copiedText: String? = null

        val result =
            toCopyResult(
                success = true,
                payload = "line 1\nline 2",
            ) { copiedText = it }

        assertEquals("line 1\nline 2", copiedText)
        assertEquals("line 1\nline 2", assertIs<CopyResult.Success>(result).text)
    }

    @Test
    fun `toCopyResult returns error when clipboard copy fails`() {
        val result =
            toCopyResult(
                success = true,
                payload = "line 1",
            ) {
                throw IllegalStateException("Clipboard unavailable")
            }

        assertEquals("Clipboard unavailable", assertIs<CopyResult.Error>(result).message)
    }

    @Test
    fun `toCopyResult preserves bridge errors without copying`() {
        var invoked = false

        val result =
            toCopyResult(
                success = false,
                payload = "No visible text to copy",
            ) {
                invoked = true
            }

        assertEquals(false, invoked)
        assertEquals("No visible text to copy", assertIs<CopyResult.Error>(result).message)
    }
}
