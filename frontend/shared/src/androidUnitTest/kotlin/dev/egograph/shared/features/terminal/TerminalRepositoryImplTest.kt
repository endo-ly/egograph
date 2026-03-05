package dev.egograph.shared.features.terminal

import dev.egograph.shared.core.data.repository.TerminalRepositoryImpl
import dev.egograph.shared.core.data.repository.internal.RepositoryClient
import dev.egograph.shared.core.domain.model.terminal.Session
import dev.egograph.shared.core.domain.model.terminal.SessionStatus
import dev.egograph.shared.core.domain.repository.ApiError
import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * TerminalRepositoryImplのテスト
 *
 * Ktor MockEngineを使用してHTTPリクエスト/レスポンスをテストします。
 */
class TerminalRepositoryImplTest {
    private val json =
        Json {
            ignoreUnknownKeys = true
            isLenient = true
        }

    private val baseUrl = "http://test.example.com"
    private val apiKey = "test-api-key"

    /**
     * テスト用HttpClientを作成する
     */
    private fun createMockHttpClient(engine: MockEngine): HttpClient =
        HttpClient(engine) {
            install(ContentNegotiation) {
                json(json)
            }
        }

    /**
     * テスト用RepositoryClientを作成する
     */
    private fun createMockRepositoryClient(engine: MockEngine): RepositoryClient {
        val httpClient = createMockHttpClient(engine)
        return RepositoryClient(httpClient, baseUrl, apiKey)
    }

    // ==================== getSessions() テスト ====================

    @Test
    fun `getSessions - success returns session list`() =
        runTest {
            // Arrange: セッション一覧レスポンスのモック設定
            val expectedResponse =
                """
                {
                    "sessions": [
                        {
                            "session_id": "session-1",
                            "name": "Test Session 1",
                            "status": "connected",
                            "last_activity": "2025-01-01T00:00:00Z",
                            "created_at": "2025-01-01T00:00:00Z"
                        },
                        {
                            "session_id": "session-2",
                            "name": "Test Session 2",
                            "status": "connected",
                            "last_activity": "2025-01-01T01:00:00Z",
                            "created_at": "2025-01-01T00:00:00Z"
                        }
                    ],
                    "count": 2
                }
                """.trimIndent()

            val mockEngine =
                MockEngine {
                    // HTTPリクエストのアサーション
                    assertEquals(HttpMethod.Get, it.method)
                    assertEquals("$baseUrl/api/v1/terminal/sessions", it.url.toString())
                    assertEquals(apiKey, it.headers["X-API-Key"])

                    respond(
                        content = expectedResponse,
                        status = HttpStatusCode.OK,
                        headers = headersOf("Content-Type", "application/json"),
                    )
                }

            val repositoryClient = createMockRepositoryClient(mockEngine)
            val repository = TerminalRepositoryImpl(repositoryClient)

            // Act: セッション一覧を収集
            val results = mutableListOf<List<Session>>()
            repository.getSessions().collect { result ->
                if (result.isSuccess) {
                    results.add(result.getOrNull()!!)
                }
            }

            // Assert: 結果の検証
            assertEquals(1, results.size)
            val actual = results[0]
            assertEquals(2, actual.size)
            assertEquals("session-1", actual[0].sessionId)
            assertEquals("Test Session 1", actual[0].name)
            assertEquals(SessionStatus.CONNECTED, actual[0].status)
            assertEquals("session-2", actual[1].sessionId)
            assertEquals("Test Session 2", actual[1].name)
            assertEquals(SessionStatus.CONNECTED, actual[1].status)
        }

    @Test
    fun `getSessions - HTTP 404 Not Found`() =
        runTest {
            // Arrange: 404 Not Foundのモック設定
            val mockEngine =
                MockEngine {
                    assertEquals(HttpMethod.Get, it.method)
                    assertEquals("$baseUrl/api/v1/terminal/sessions", it.url.toString())

                    respond(
                        content = """{"detail": "Sessions not found"}""",
                        status = HttpStatusCode.NotFound,
                        headers = headersOf("Content-Type", "application/json"),
                    )
                }

            val repositoryClient = createMockRepositoryClient(mockEngine)
            val repository = TerminalRepositoryImpl(repositoryClient)

            // Act: エラー結果を収集
            val errors = mutableListOf<ApiError>()
            repository.getSessions().collect { result ->
                if (result.isFailure) {
                    result.exceptionOrNull()?.let {
                        assertIs<ApiError>(it)
                        errors.add(it)
                    }
                }
            }

            // Assert
            assertTrue(errors.isNotEmpty())
            val error = assertIs<ApiError.HttpError>(errors.first())
            assertEquals(404, error.code)
        }

    @Test
    fun `getSessions - HTTP 500 Internal Server Error`() =
        runTest {
            // Arrange: 500 Internal Server Errorのモック設定
            val mockEngine =
                MockEngine {
                    respond(
                        content = """{"detail": "Internal server error"}""",
                        status = HttpStatusCode.InternalServerError,
                        headers = headersOf("Content-Type", "application/json"),
                    )
                }

            val repositoryClient = createMockRepositoryClient(mockEngine)
            val repository = TerminalRepositoryImpl(repositoryClient)

            // Act: エラー結果を収集
            val errors = mutableListOf<ApiError>()
            repository.getSessions().collect { result ->
                if (result.isFailure) {
                    result.exceptionOrNull()?.let {
                        assertIs<ApiError>(it)
                        errors.add(it)
                    }
                }
            }

            // Assert
            assertTrue(errors.isNotEmpty())
            val error = assertIs<ApiError.HttpError>(errors.first())
            assertEquals(500, error.code)
        }

    @Test
    fun `getSessions - empty session list`() =
        runTest {
            // Arrange: 空のセッションリストのモック設定
            val expectedResponse =
                """
                {
                    "sessions": [],
                    "count": 0
                }
                """.trimIndent()

            val mockEngine =
                MockEngine {
                    respond(
                        content = expectedResponse,
                        status = HttpStatusCode.OK,
                        headers = headersOf("Content-Type", "application/json"),
                    )
                }

            val repositoryClient = createMockRepositoryClient(mockEngine)
            val repository = TerminalRepositoryImpl(repositoryClient)

            // Act
            val results = mutableListOf<List<Session>>()
            repository.getSessions().collect { result ->
                if (result.isSuccess) {
                    results.add(result.getOrNull()!!)
                }
            }

            // Assert
            assertEquals(1, results.size)
            val actual = results[0]
            assertTrue(actual.isEmpty())
        }

    // ==================== issueWsToken() テスト ====================

    @Test
    fun `issueWsToken - success returns ws token`() =
        runTest {
            // Arrange: WebSocket トークン発行レスポンスのモック設定
            val sessionId = "test-session-123"
            val expectedResponse =
                """
                {
                    "ws_token": "test-ws-token-abc456",
                    "expires_in_seconds": 3600
                }
                """.trimIndent()

            val mockEngine =
                MockEngine {
                    // HTTPリクエストのアサーション
                    assertEquals(HttpMethod.Post, it.method)
                    assertEquals("$baseUrl/api/v1/terminal/sessions/$sessionId/ws-token", it.url.toString())
                    assertEquals(apiKey, it.headers["X-API-Key"])

                    respond(
                        content = expectedResponse,
                        status = HttpStatusCode.OK,
                        headers = headersOf("Content-Type", "application/json"),
                    )
                }

            val repositoryClient = createMockRepositoryClient(mockEngine)
            val repository = TerminalRepositoryImpl(repositoryClient)

            // Act: WebSocket トークンを発行
            val result = repository.issueWsToken(sessionId)

            // Assert: 結果の検証
            assertTrue(result.isSuccess)
            val actual = result.getOrNull()!!
            assertEquals("test-ws-token-abc456", actual.wsToken)
            assertEquals(3600, actual.expiresInSeconds)
        }

    @Test
    fun `issueWsToken - HTTP 401 Unauthorized`() =
        runTest {
            // Arrange: 401 Unauthorizedのモック設定
            val sessionId = "test-session-123"

            val mockEngine =
                MockEngine {
                    assertEquals(HttpMethod.Post, it.method)
                    assertEquals("$baseUrl/api/v1/terminal/sessions/$sessionId/ws-token", it.url.toString())

                    respond(
                        content = """{"detail": "Invalid API key"}""",
                        status = HttpStatusCode.Unauthorized,
                        headers = headersOf("Content-Type", "application/json"),
                    )
                }

            val repositoryClient = createMockRepositoryClient(mockEngine)
            val repository = TerminalRepositoryImpl(repositoryClient)

            // Act: エラー結果を取得
            val result = repository.issueWsToken(sessionId)

            // Assert
            assertTrue(result.isFailure)
            val error = assertIs<ApiError.HttpError>(result.exceptionOrNull()!!)
            assertEquals(401, error.code)
        }

    @Test
    fun `issueWsToken - HTTP 404 Not Found`() =
        runTest {
            // Arrange: 404 Not Foundのモック設定
            val sessionId = "non-existent-session"

            val mockEngine =
                MockEngine {
                    assertEquals(HttpMethod.Post, it.method)
                    assertEquals("$baseUrl/api/v1/terminal/sessions/$sessionId/ws-token", it.url.toString())

                    respond(
                        content = """{"detail": "Session not found"}""",
                        status = HttpStatusCode.NotFound,
                        headers = headersOf("Content-Type", "application/json"),
                    )
                }

            val repositoryClient = createMockRepositoryClient(mockEngine)
            val repository = TerminalRepositoryImpl(repositoryClient)

            // Act: エラー結果を取得
            val result = repository.issueWsToken(sessionId)

            // Assert
            assertTrue(result.isFailure)
            val error = assertIs<ApiError.HttpError>(result.exceptionOrNull()!!)
            assertEquals(404, error.code)
        }
}
