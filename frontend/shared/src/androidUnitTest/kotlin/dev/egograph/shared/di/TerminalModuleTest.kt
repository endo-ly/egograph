package dev.egograph.shared.di

import dev.egograph.shared.core.domain.repository.TerminalRepository
import dev.egograph.shared.core.platform.PlatformPreferences
import dev.egograph.shared.core.platform.PlatformPrefsKeys
import io.ktor.client.HttpClient
import io.mockk.every
import io.mockk.mockk
import org.koin.core.context.startKoin
import org.koin.core.context.stopKoin
import org.koin.dsl.module
import org.koin.test.KoinTest
import org.koin.test.inject
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertNotNull

class TerminalModuleTest : KoinTest {
    @AfterTest
    fun tearDown() {
        stopKoin()
    }

    @Test
    fun `TerminalRepository should be injectable`() {
        startKoin {
            modules(testModule())
        }

        val repository: TerminalRepository by inject()
        assertNotNull(repository)
    }

    @Test
    fun `HttpClient should be injectable`() {
        startKoin {
            modules(testModule())
        }

        val httpClient: HttpClient by inject()
        assertNotNull(httpClient)
    }

    private fun testModule() =
        listOf(
            module {
                val mockPreferences = mockk<PlatformPreferences>()
                every { mockPreferences.getString(PlatformPrefsKeys.KEY_GATEWAY_API_URL, any()) } returns "http://localhost:8001"
                every { mockPreferences.getString(PlatformPrefsKeys.KEY_API_KEY, any()) } returns "test-api-key"

                single { HttpClient() }
                single { mockPreferences }
            },
            terminalModule,
        )
}
