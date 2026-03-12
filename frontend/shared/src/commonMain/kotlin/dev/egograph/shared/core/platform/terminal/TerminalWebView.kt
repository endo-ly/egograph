package dev.egograph.shared.core.platform.terminal

import kotlinx.coroutines.flow.Flow

/**
 * Result of a copy operation
 */
sealed interface CopyResult {
    /**
     * Copy succeeded with the copied text
     */
    data class Success(
        val text: String,
    ) : CopyResult

    /**
     * Copy failed with an error message
     */
    data class Error(
        val message: String,
    ) : CopyResult
}

/**
 * Terminal WebView interface for platform-specific implementations
 *
 * Provides WebView functionality for rendering xterm.js terminal
 * and handling JavaScript bridge communication.
 */
interface TerminalWebView {
    /**
     * Load the terminal.html file from assets
     */
    fun loadTerminal()

    /**
     * Connect to WebSocket endpoint
     *
     * @param wsUrl WebSocket URL to connect to
     * @param wsToken WebSocket authentication token for post-connect authentication
     */
    fun connect(
        wsUrl: String,
        wsToken: String,
    )

    /**
     * Disconnect from WebSocket
     */
    fun disconnect()

    /**
     * Send a special key sequence to the terminal
     *
     * @param key Key sequence to send (e.g., "\u0001" for Ctrl+A)
     */
    fun sendKey(key: String)

    /**
     * Focus terminal input and move viewport to the latest line.
     *
     * Used when software keyboard becomes visible so input always targets
     * the current prompt at the bottom.
     */
    fun focusInputAtBottom()

    fun setKeyboardVisible(visible: Boolean)

    /**
     * Apply terminal color theme.
     *
     * @param darkMode true for dark theme, false for light theme
     */
    fun setTheme(darkMode: Boolean)

    /**
     * Copy currently visible terminal text to clipboard.
     *
     * Results are emitted through the copyResults flow.
     */
    fun copyVisibleText()

    /**
     * Flow of connection state changes
     * Emits true when connected, false when disconnected
     */
    val connectionState: Flow<Boolean>

    /**
     * Flow of errors
     * Emits error messages
     */
    val errors: Flow<String>

    /**
     * Flow of copy operation results
     * Emits CopyResult.Success or CopyResult.Error
     */
    val copyResults: Flow<CopyResult>
}

/**
 * Factory for creating TerminalWebView instances
 */
expect fun createTerminalWebView(): TerminalWebView
