package ru.natoday.app

import android.app.Application
import androidx.room.Room
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import ru.natoday.app.data.SettingsRepository
import ru.natoday.app.data.TaskDatabase
import ru.natoday.app.data.TaskRepository
import ru.natoday.app.reminders.ReminderScheduler

class PlannerApplication : Application() {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    val database by lazy { Room.databaseBuilder(this, TaskDatabase::class.java, "tasks.db").build() }
    val tasks by lazy { TaskRepository(database.tasks()) }
    val settings by lazy { SettingsRepository(this) }
    val reminders by lazy { ReminderScheduler(this, settings) }
}
