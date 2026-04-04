package dev.egograph.shared.di

import dev.egograph.shared.cache.DiskCache
import dev.egograph.shared.cache.DiskCacheContext
import dev.egograph.shared.core.data.repository.ChatRepositoryImpl
import dev.egograph.shared.core.data.repository.MessageRepositoryImpl
import dev.egograph.shared.core.data.repository.SystemPromptRepositoryImpl
import dev.egograph.shared.core.data.repository.ThreadRepositoryImpl
import dev.egograph.shared.core.data.repository.internal.InMemoryCache
import dev.egograph.shared.core.data.repository.internal.RepositoryClient
import dev.egograph.shared.core.domain.repository.ChatRepository
import dev.egograph.shared.core.domain.repository.MessageRepository
import dev.egograph.shared.core.domain.repository.SystemPromptRepository
import dev.egograph.shared.core.domain.repository.ThreadRepository
import dev.egograph.shared.core.network.HttpClientConfig
import dev.egograph.shared.core.network.HttpClientConfigProvider
import dev.egograph.shared.core.network.provideHttpClient
import dev.egograph.shared.core.platform.PlatformPreferences
import dev.egograph.shared.core.platform.PlatformPrefsDefaults
import dev.egograph.shared.core.platform.PlatformPrefsKeys
import dev.egograph.shared.core.platform.getDefaultBaseUrl
import dev.egograph.shared.core.platform.normalizeBaseUrl
import dev.egograph.shared.core.settings.ThemeRepository
import dev.egograph.shared.core.settings.ThemeRepositoryImpl
import dev.egograph.shared.features.chat.ChatScreenModel
import dev.egograph.shared.features.settings.SettingsScreenModel
import dev.egograph.shared.features.systemprompt.SystemPromptEditorScreenModel
import io.ktor.client.HttpClient
import org.koin.core.qualifier.named
import org.koin.dsl.module

/**
 * Application-wide DI module
 *
 * Provides all application dependencies using Koin's traditional module definition.
 */
val appModule =
    module {
        // === Configuration ===
        single<String>(qualifier = named("BaseUrl")) {
            val preferences = getOrNull<PlatformPreferences>()
            val savedUrl = preferences?.getString(PlatformPrefsKeys.KEY_API_URL, PlatformPrefsDefaults.DEFAULT_API_URL)
            val rawUrl = if (savedUrl.isNullOrBlank()) getDefaultBaseUrl() else savedUrl
            try {
                normalizeBaseUrl(rawUrl)
            } catch (e: IllegalArgumentException) {
                getDefaultBaseUrl()
            }
        }

        single<String>(qualifier = named("ApiKey")) {
            val preferences = getOrNull<PlatformPreferences>()
            preferences?.getString(PlatformPrefsKeys.KEY_API_KEY, PlatformPrefsDefaults.DEFAULT_API_KEY) ?: ""
        }

        // === HTTP Client Configuration ===
        single<HttpClientConfigProvider> { HttpClientConfigProvider() }

        single<HttpClientConfig> {
            get<HttpClientConfigProvider>().getConfig()
        }

        // === Core ===
        single<HttpClient> {
            provideHttpClient(get<HttpClientConfig>())
        }

        single<DiskCache?> {
            val context = getOrNull<DiskCacheContext>()
            context?.let { DiskCache(it) }
        }

        // === RepositoryClient (Backend API) ===
        single<RepositoryClient>(qualifier = named("BackendClient")) {
            RepositoryClient(
                httpClient = get(),
                baseUrl = get(qualifier = named("BaseUrl")),
                apiKey = get(qualifier = named("ApiKey")),
            )
        }

        // === Cache ===
        single<InMemoryCache<String, Any>> { InMemoryCache() }

        // === Repositories ===
        single<ThreadRepository> {
            ThreadRepositoryImpl(
                repositoryClient = get(qualifier = named("BackendClient")),
                diskCache = getOrNull(),
            )
        }

        single<SystemPromptRepository> {
            SystemPromptRepositoryImpl(
                repositoryClient = get(qualifier = named("BackendClient")),
                diskCache = getOrNull(),
            )
        }

        single<MessageRepository> {
            MessageRepositoryImpl(
                repositoryClient = get(qualifier = named("BackendClient")),
                diskCache = getOrNull(),
            )
        }

        single<ChatRepository> {
            ChatRepositoryImpl(
                repositoryClient = get(qualifier = named("BackendClient")),
                httpClientConfig = get<HttpClientConfig>(),
            )
        }

        single<ThemeRepository> {
            ThemeRepositoryImpl(preferences = get())
        }

        // === ScreenModels ===
        single {
            ChatScreenModel(
                threadRepository = get(),
                messageRepository = get(),
                chatRepository = get(),
                preferences = get(),
            )
        }

        factory {
            SystemPromptEditorScreenModel(
                repository = get(),
            )
        }

        factory {
            SettingsScreenModel(
                preferences = get(),
                themeRepository = get(),
            )
        }
    }
