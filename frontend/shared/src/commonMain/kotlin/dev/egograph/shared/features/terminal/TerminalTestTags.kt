package dev.egograph.shared.features.terminal

/**
 * Terminal機能用のテストタグ定数
 *
 * Maestro E2EテストおよびCompose UIテストで使用する安定したタグ名を定義します。
 * これらのタグは `testTagsAsResourceId = true` と共に使用され、
 * リソースIDとしてAndroid UI Automationからアクセス可能です。
 */
object TerminalTestTags {
    /** セッションリストアイテムのルートタグ */
    const val SESSION_ITEM = "session_item"

    /** セッションプレビュー（ターミナルスナップショット表示）のタグ */
    const val SESSION_PREVIEW = "session_preview"

    /** ターミナル接続状態を示すステータスピルのタグ */
    const val TERMINAL_STATUS_PILL = "terminal_status_pill"

    /** ターミナル画面の戻るボタンのタグ */
    const val TERMINAL_BACK_BUTTON = "terminal_back_button"

    /** ターミナルキーボードの表示/非表示を切り替えるボタンのタグ */
    const val TERMINAL_KEYBOARD_TOGGLE = "terminal_keyboard_toggle"

    /** ターミナル内容をコピーするボタンのタグ */
    const val TERMINAL_COPY_BUTTON = "terminal_copy_button"

    /** コピー完了フィードバック（トースト等）のタグ */
    const val TERMINAL_COPY_FEEDBACK = "terminal_copy_feedback"
}
