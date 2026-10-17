package ru.natoday.app.ui

import android.Manifest
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.natoday.app.R
import ru.natoday.app.reminders.ReminderScheduler
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(vm: SettingsViewModel, scheduler: ReminderScheduler, onBack: () -> Unit) {
    val state by vm.settings.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val error by vm.error.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var allowed by remember { mutableStateOf(scheduler.notificationsAllowed()) }
    var timePicker by rememberSaveable { mutableStateOf(false) }
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { allowed = scheduler.notificationsAllowed() }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        allowed = scheduler.notificationsAllowed()
        vm.enabled(true)
    }
    val switchDescription = stringResource(R.string.reminder_enabled)
    Scaffold(topBar = {
        TopAppBar(title = { Text(stringResource(R.string.settings)) }, navigationIcon = { ActionIcon(R.drawable.ic_back, R.string.back, action = onBack) })
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Text(stringResource(R.string.reminder_heading), style = MaterialTheme.typography.headlineSmall)
            Text(stringResource(R.string.reminder_description))
            state?.let { prefs ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.reminder_enabled), Modifier.weight(1f))
                    Switch(prefs.enabled, onCheckedChange = {
                        if (it && Build.VERSION.SDK_INT >= 33 && !allowed) permission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        else vm.enabled(it)
                    }, enabled = !busy, modifier = Modifier.semantics { contentDescription = switchDescription })
                }
                OutlinedButton(onClick = { timePicker = true }, enabled = !busy) {
                    Text(stringResource(R.string.reminder_time, prefs.time.format(DateTimeFormatter.ofPattern("HH:mm"))))
                }
                if (timePicker) ChooseTime(prefs.time, { timePicker = false }) { vm.time(it); timePicker = false }
            } ?: Text(stringResource(R.string.loading))
            Text(stringResource(R.string.reminder_approximate))
            if (!allowed) {
                Card { Text(stringResource(R.string.notifications_blocked), Modifier.padding(16.dp)) }
                OutlinedButton(onClick = {
                    context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
                }) { Text(stringResource(R.string.open_notification_settings)) }
            }
            if (error) Text(stringResource(R.string.reminder_error), color = MaterialTheme.colorScheme.error)
            HorizontalDivider()
            Text(stringResource(R.string.local_storage), style = MaterialTheme.typography.bodySmall)
        }
    }
}
