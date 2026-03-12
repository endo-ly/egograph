package dev.egograph.shared.core.ui.common

import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.ExperimentalTime
import kotlin.time.Instant

@OptIn(ExperimentalTime::class)
class DateTimeTextTest {
    private fun expectedLocalText(isoString: String): String {
        val localDateTime = Instant.parse(isoString).toLocalDateTime(TimeZone.currentSystemDefault())

        @Suppress("DEPRECATION")
        val month = localDateTime.monthNumber.toString().padStart(2, '0')

        @Suppress("DEPRECATION")
        val day = localDateTime.dayOfMonth.toString().padStart(2, '0')
        val hour = localDateTime.hour.toString().padStart(2, '0')
        val minute = localDateTime.minute.toString().padStart(2, '0')
        return "$month/$day $hour:$minute"
    }

    @Test
    fun `toCompactIsoDateTime formats standard iso datetime`() {
        val input = "2026-02-24T13:30:45Z"

        val result = input.toCompactIsoDateTime()

        assertEquals(expectedLocalText(input), result)
    }

    @Test
    fun `toCompactIsoDateTime returns original when too short`() {
        val input = "2026-02-24"

        val result = input.toCompactIsoDateTime()

        assertEquals(input, result)
    }

    @Test
    fun `toCompactIsoDateTime trims nothing and preserves invalid text`() {
        val input = "not-a-date"

        val result = input.toCompactIsoDateTime()

        assertEquals(input, result)
    }

    @Test
    fun `toCompactIsoDateTime handles offset format`() {
        val input = "2026-02-24T07:05:00+09:00"

        val result = input.toCompactIsoDateTime()

        assertEquals(expectedLocalText(input), result)
    }
}
