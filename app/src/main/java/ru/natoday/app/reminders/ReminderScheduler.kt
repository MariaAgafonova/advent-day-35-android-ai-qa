package ru.natoday.app.reminders

import android.Manifest
import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import ru.natoday.app.MainActivity
import ru.natoday.app.R
import ru.natoday.app.data.ScheduledReminder
import ru.natoday.app.data.SettingsRepository
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.util.UUID

class ReminderScheduler(private val context: Context, private val settings: SettingsRepository) {
    private val mutex = Mutex()
    private val alarms = context.getSystemService(AlarmManager::class.java)
    private val manager = context.getSystemService(NotificationManager::class.java)

    init {
        manager.createNotificationChannel(NotificationChannel(CHANNEL, context.getString(R.string.reminder_channel), NotificationManager.IMPORTANCE_DEFAULT))
    }
    fun notificationsAllowed(): Boolean =
        (Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) &&
            NotificationManagerCompat.from(context).areNotificationsEnabled() &&
            manager.getNotificationChannel(CHANNEL)?.importance != NotificationManager.IMPORTANCE_NONE

    private fun alarmIntent(value: ScheduledReminder? = null): PendingIntent {
        val intent = Intent(context, ReminderReceiver::class.java).setAction(ACTION_REMIND)
        value?.let {
            intent.putExtra(EXTRA_TOKEN, it.token)
            intent.putExtra(EXTRA_DAY, it.day)
            intent.putExtra(EXTRA_AT, it.at)
        }
        return PendingIntent.getBroadcast(context, 31, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    suspend fun setEnabled(enabled: Boolean) = mutex.withLock {
        settings.setEnabled(enabled)
        scheduleLocked()
    }
    suspend fun setTime(time: LocalTime) = mutex.withLock {
        settings.setTime(time)
        scheduleLocked()
    }
    suspend fun reschedule() = mutex.withLock { scheduleLocked() }

    suspend fun ensureScheduled() = mutex.withLock {
        val prefs = settings.settings.first()
        val existing = settings.scheduled.first()
        val zone = ZoneId.systemDefault()
        val today = LocalDate.now(zone)
        val existingTime = existing?.let { Instant.ofEpochMilli(it.at).atZone(zone) }
        if (prefs.enabled && existing != null && existingTime != null &&
            existingTime.toLocalTime() == prefs.time && existingTime.toLocalDate() >= today) {
            alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, existing.at, alarmIntent(existing))
        } else scheduleLocked()
    }

    private suspend fun scheduleLocked() {
        alarms.cancel(alarmIntent())
        val prefs = settings.settings.first()
        if (!prefs.enabled) {
            settings.recordSchedule(null)
            manager.cancel(NOTIFICATION_ID)
            return
        }
        val moment = nextReminder(Instant.now(), prefs.time, ZoneId.systemDefault())
        val value = ScheduledReminder(UUID.randomUUID().toString(), moment.date.toEpochDay(), moment.instant.toEpochMilli())
        settings.recordSchedule(value)
        try {
            alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, value.at, alarmIntent(value))
        } catch (error: RuntimeException) {
            settings.recordSchedule(null)
            throw error
        }
    }

    suspend fun deliver(token: String, day: Long, at: Long) = mutex.withLock {
        val value = settings.scheduled.first()
        if (value == null || value.token != token || value.day != day || value.at != at) return@withLock
        if (settings.claimDelivery(value) && notificationsAllowed()) {
            val launch = Intent(context, MainActivity::class.java)
                .setAction(ACTION_REVIEW)
                .putExtra(EXTRA_DAY, day)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            val pending = PendingIntent.getActivity(context, 32, launch, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            val notification = NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(R.drawable.ic_reminder)
                .setContentTitle(context.getString(R.string.notification_title))
                .setContentText(context.getString(R.string.notification_text))
                .setStyle(NotificationCompat.BigTextStyle().bigText(context.getString(R.string.notification_text)))
                .setSubText(LocalDate.ofEpochDay(day).toString())
                .setContentIntent(pending)
                .setAutoCancel(true)
                .build()
            try { manager.notify(NOTIFICATION_ID, notification) } catch (_: SecurityException) { /* Permission can change while posting. */ }
        }
        scheduleLocked()
    }

    companion object {
        const val CHANNEL = "evening_review"
        const val NOTIFICATION_ID = 31
        const val ACTION_REMIND = "ru.natoday.app.REMIND"
        const val ACTION_REVIEW = "ru.natoday.app.REVIEW"
        const val EXTRA_DAY = "review_day"
        const val EXTRA_AT = "alarm_at"
        const val EXTRA_TOKEN = "alarm_token"
    }
}
