package ru.natoday.app.reminders

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout
import ru.natoday.app.PlannerApplication

class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pending = goAsync()
        val app = context.applicationContext as PlannerApplication
        app.scope.launch {
            try {
                withTimeout(8_000) {
                    if (intent.action == ReminderScheduler.ACTION_REMIND) {
                        val token = intent.getStringExtra(ReminderScheduler.EXTRA_TOKEN) ?: return@withTimeout
                        app.reminders.deliver(token,
                            intent.getLongExtra(ReminderScheduler.EXTRA_DAY, Long.MIN_VALUE),
                            intent.getLongExtra(ReminderScheduler.EXTRA_AT, Long.MIN_VALUE))
                    } else {
                        app.reminders.reschedule()
                    }
                }
            } catch (error: Exception) {
                Log.e("ReminderReceiver", "Unable to schedule reminder", error)
            } finally { pending.finish() }
        }
    }
}
