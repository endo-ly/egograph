package dev.egograph.shared.core.ui.common

import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlin.time.ExperimentalTime
import kotlin.time.Instant

@OptIn(ExperimentalTime::class)
internal fun String.toCompactIsoDateTime(): String =
    runCatching {
        val localDateTime = Instant.parse(this).toLocalDateTime(TimeZone.currentSystemDefault())

        @Suppress("DEPRECATION")
        val month = localDateTime.monthNumber.toString().padStart(2, '0')

        @Suppress("DEPRECATION")
        val day = localDateTime.dayOfMonth.toString().padStart(2, '0')
        val hour = localDateTime.hour.toString().padStart(2, '0')
        val minute = localDateTime.minute.toString().padStart(2, '0')
        val datePart = "$month/$day"
        val timePart = "$hour:$minute"
        "$datePart $timePart"
    }.getOrElse { this }
