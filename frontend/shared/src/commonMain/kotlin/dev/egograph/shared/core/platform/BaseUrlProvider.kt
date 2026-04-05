package dev.egograph.shared.core.platform

expect fun getDefaultBaseUrl(): String

/**
 * APIのベースURLを正規化する。
 *
 * 入力されたURLの末尾スラッシュを削除する。
 *
 * @param url 正規化対象のURL
 * @return 末尾スラッシュを削除したURL
 *
 * @throws IllegalArgumentException URLが空、または `http://` / `https://` で始まらない場合
 */
fun normalizeBaseUrl(url: String): String {
    val trimmed = url.trim()
    require(trimmed.isNotBlank()) { "URL cannot be blank" }
    require(trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
        "URL must start with http:// or https://"
    }

    // 末尾スラッシュのみ削除
    return trimmed.trimEnd('/')
}

/**
 * URLが有効かどうかを検証する。
 *
 * @param url 検証対象のURL
 * @return 有効な場合はtrue、それ以外はfalse
 */
fun isValidUrl(url: String): Boolean {
    val trimmed = url.trim()
    if (trimmed.isEmpty()) return false
    val hasValidScheme = trimmed.startsWith("http://") || trimmed.startsWith("https://")
    val hostPortPart = trimmed.substringAfter("://", missingDelimiterValue = "")
    return hasValidScheme && hostPortPart.isNotBlank()
}
