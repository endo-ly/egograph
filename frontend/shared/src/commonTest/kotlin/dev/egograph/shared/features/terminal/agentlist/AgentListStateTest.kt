package dev.egograph.shared.features.terminal.agentlist

import kotlin.test.Test
import kotlin.test.assertEquals

class AgentListStateTest {
    @Test
    fun `AgentListState starts with empty sessions`() {
        val state = AgentListState()

        assertEquals(0, state.sessions.size)
    }

    @Test
    fun `AgentListState keeps loading and error flags`() {
        val state = AgentListState(isLoadingSessions = true, sessionsError = "failed")

        assertEquals(true, state.isLoadingSessions)
        assertEquals("failed", state.sessionsError)
    }
}
