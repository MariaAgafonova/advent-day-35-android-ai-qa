package ru.natoday.app

import org.junit.Assert.*
import org.junit.Test
import ru.natoday.app.data.TaskConverters
import ru.natoday.app.reminders.nextReminder
import ru.natoday.app.reminders.tomorrowForReview
import ru.natoday.app.voice.VoiceParser
import ru.natoday.app.voice.SpeechInput
import android.speech.SpeechRecognizer
import java.time.*

class LogicTest {
    @Test fun explicitVoiceSeparatorOnly() {
        assertEquals(listOf("Купить продукты", "закончить отчёт", "позвонить маме"),
            VoiceParser.split("Купить продукты новая задача закончить отчёт новая задача позвонить маме"))
        assertEquals(listOf("Купить хлеб и молоко, забрать письмо"), VoiceParser.split("Купить хлеб и молоко, забрать письмо"))
    }
    @Test fun voiceHandlesCaseWhitespaceAndEmptyPieces() {
        assertEquals(listOf("Звонок", "Письмо"), VoiceParser.split("новая задача  Звонок. НОВАЯ   ЗАДАЧА Письмо новая задача"))
        assertEquals(emptyList<String>(), VoiceParser.split("   новая задача  "))
        assertEquals(listOf("новая задачами"), VoiceParser.split("новая задачами"))
        assertEquals(listOf("Первое", "Второе"), VoiceParser.splitLines("Первое\nВторое"))
    }
    @Test fun reviewTomorrowUsesReviewDateAcrossBoundaries() {
        assertEquals(LocalDate.of(2027, 1, 1), tomorrowForReview(LocalDate.of(2026, 12, 31)))
        assertEquals(LocalDate.of(2028, 2, 29), tomorrowForReview(LocalDate.of(2028, 2, 28)))
        assertEquals(LocalDate.of(2028, 3, 1), tomorrowForReview(LocalDate.of(2028, 2, 29)))
        assertEquals(LocalDate.of(2026, 5, 1), tomorrowForReview(LocalDate.of(2026, 4, 30)))
    }
    @Test fun nextAlarmIsFutureAndUsesLocalTime() {
        val now = Instant.parse("2026-10-15T18:00:00Z")
        val result = nextReminder(now, LocalTime.of(22, 0), ZoneId.of("Europe/Belgrade"))
        assertEquals(LocalDate.of(2026, 10, 15), result.date)
        assertEquals(Instant.parse("2026-10-15T20:00:00Z"), result.instant)
        assertEquals(LocalDate.of(2026, 10, 16), nextReminder(result.instant, LocalTime.of(22, 0), ZoneId.of("Europe/Belgrade")).date)
    }
    @Test fun timeZoneAndDstAreRecalculated() {
        val now = Instant.parse("2026-10-15T09:00:00Z")
        val belgrade = nextReminder(now, LocalTime.of(22, 0), ZoneId.of("Europe/Belgrade"))
        val tokyo = nextReminder(now, LocalTime.of(22, 0), ZoneId.of("Asia/Tokyo"))
        assertNotEquals(belgrade.instant, tokyo.instant)
        val gap = nextReminder(Instant.parse("2026-03-29T00:00:00Z"), LocalTime.of(2, 30), ZoneId.of("Europe/Belgrade"))
        assertEquals(Instant.parse("2026-03-29T01:30:00Z"), gap.instant)
        val overlap = nextReminder(Instant.parse("2026-10-25T01:15:00Z"), LocalTime.of(2, 30), ZoneId.of("Europe/Belgrade"))
        assertTrue(overlap.instant > Instant.parse("2026-10-25T01:15:00Z"))
    }
    @Test fun datesAndTimestampsHaveSeparateStorageSemantics() {
        val converter = TaskConverters()
        val date = LocalDate.of(2028, 2, 29)
        val instant = Instant.parse("2028-02-28T23:30:00Z")
        assertEquals(date, converter.longToDate(converter.dateToLong(date)))
        assertEquals(instant, converter.longToInstant(converter.instantToLong(instant)))
        assertNull(converter.longToInstant(null))
        assertEquals(date.toEpochDay(), converter.dateToLong(date))
    }
    @Test fun voiceFailuresMapToActionableMessages() {
        assertEquals(R.string.voice_permission_denied, SpeechInput.errorResource(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS))
        assertEquals(R.string.voice_no_speech, SpeechInput.errorResource(SpeechRecognizer.ERROR_SPEECH_TIMEOUT))
        assertEquals(R.string.voice_network, SpeechInput.errorResource(SpeechRecognizer.ERROR_NETWORK_TIMEOUT))
        assertEquals(R.string.voice_language, SpeechInput.errorResource(SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED))
    }
}
