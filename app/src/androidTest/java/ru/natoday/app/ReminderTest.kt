package ru.natoday.app

import android.app.NotificationManager
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import java.time.LocalTime

class ReminderTest {
    private val app = ApplicationProvider.getApplicationContext<PlannerApplication>()
    @After fun cleanup() = runBlocking { app.reminders.setEnabled(false) }

    @Test fun enablingChangingTimeAndDisablingReplaceOneSchedule() = runBlocking {
        app.reminders.setEnabled(false)
        assertNull(app.settings.scheduled.first())
        app.reminders.setTime(LocalTime.of(22, 0))
        app.reminders.setEnabled(true)
        val original = app.settings.scheduled.first()!!
        app.reminders.setTime(LocalTime.of(21, 17))
        val changed = app.settings.scheduled.first()!!
        assertNotEquals(original.token, changed.token)
        assertNotEquals(original.at, changed.at)
        app.reminders.deliver(original.token, original.day, original.at)
        assertEquals(changed, app.settings.scheduled.first())
        app.reminders.ensureScheduled()
        assertEquals(changed, app.settings.scheduled.first())
        app.reminders.setEnabled(false)
        assertNull(app.settings.scheduled.first())
        assertFalse(app.settings.settings.first().enabled)
        assertTrue(app.getSystemService(NotificationManager::class.java).activeNotifications.none { it.id == 31 })
    }
}
