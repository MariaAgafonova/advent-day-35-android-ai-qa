package ru.natoday.app.reminders

import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId

data class ReminderMoment(val date: LocalDate, val instant: Instant)

fun nextReminder(now: Instant, time: LocalTime, zone: ZoneId): ReminderMoment {
    val today = now.atZone(zone).toLocalDate()
    var date = today
    var instant = date.atTime(time).atZone(zone).toInstant()
    if (!instant.isAfter(now)) {
        date = date.plusDays(1)
        instant = date.atTime(time).atZone(zone).toInstant()
    }
    return ReminderMoment(date, instant)
}

fun tomorrowForReview(date: LocalDate): LocalDate = date.plusDays(1)
