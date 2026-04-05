package dev.egograph.shared.core.platform

import dev.egograph.shared.BuildConfig

actual fun getDefaultBaseUrl(): String =
    when (BuildConfig.BUILD_TYPE) {
        "debug" -> BuildConfig.DEBUG_BASE_URL
        "staging" ->
            if (BuildConfig.STAGING_BASE_URL.isNotBlank()) {
                BuildConfig.STAGING_BASE_URL
            } else {
                BuildConfig.DEBUG_BASE_URL
            }
        else ->
            if (BuildConfig.RELEASE_BASE_URL.isNotBlank()) {
                BuildConfig.RELEASE_BASE_URL
            } else if (BuildConfig.STAGING_BASE_URL.isNotBlank()) {
                BuildConfig.STAGING_BASE_URL
            } else {
                BuildConfig.DEBUG_BASE_URL
            }
    }
