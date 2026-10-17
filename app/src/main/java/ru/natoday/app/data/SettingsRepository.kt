package ru.natoday.app.data

import android.content.Context
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.LocalTime

internal val Context.settingsStore by preferencesDataStore("settings")

data class ReminderSettings(val enabled: Boolean = false, val time: LocalTime = LocalTime.of(22, 0))
data class ScheduledReminder(val token: String, val day: Long, val at: Long)

class SettingsRepository(context: Context) {
    private val store = context.applicationContext.settingsStore
    private val enabled = booleanPreferencesKey("reminder_enabled")
    private val minutes = intPreferencesKey("reminder_minutes")
    private val token = stringPreferencesKey("alarm_token")
    private val day = longPreferencesKey("alarm_day")
    private val at = longPreferencesKey("alarm_at")
    private val deliveredDay = longPreferencesKey("delivered_day")
    val settings: Flow<ReminderSettings> = store.data.map {
        ReminderSettings(it[enabled] ?: false, LocalTime.ofSecondOfDay(((it[minutes] ?: 1320).coerceIn(0, 1439) * 60).toLong()))
    }
    val scheduled: Flow<ScheduledReminder?> = store.data.map { p ->
        p[token]?.let { ScheduledReminder(it, p[day] ?: return@map null, p[at] ?: return@map null) }
    }
    suspend fun setEnabled(value: Boolean) { store.edit { it[enabled] = value } }
    suspend fun setTime(value: LocalTime) { store.edit { it[minutes] = value.hour * 60 + value.minute } }
    suspend fun recordSchedule(value: ScheduledReminder?) {
        store.edit { p ->
            if (value == null) { p.remove(token); p.remove(day); p.remove(at) }
            else { p[token] = value.token; p[day] = value.day; p[at] = value.at }
        }
    }
    suspend fun claimDelivery(value: ScheduledReminder): Boolean {
        var claimed = false
        store.edit { p ->
            if (p[token] == value.token && p[enabled] == true && p[deliveredDay] != value.day) {
                p[deliveredDay] = value.day
                claimed = true
            }
        }
        return claimed
    }
}
