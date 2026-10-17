package ru.natoday.app.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.net.toUri
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.natoday.app.R
import ru.natoday.app.voice.SpeechInput
import ru.natoday.app.voice.VoiceParser

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceScreen(vm: VoiceViewModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val raw by vm.raw.collectAsStateWithLifecycle()
    val lines by vm.lines.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var listening by remember { mutableStateOf(false) }
    var error by rememberSaveable { mutableStateOf<Int?>(null) }
    var splitIndex by rememberSaveable { mutableStateOf<Int?>(null) }
    var splitText by rememberSaveable { mutableStateOf("") }
    val snackbar = remember { SnackbarHostState() }
    TaskEvents(vm, snackbar, onBack)
    val speech = remember(vm, context) {
        SpeechInput(context, { vm.recognized(it); error = null }, { error = it }, { listening = it })
    }
    DisposableEffect(speech) { onDispose { speech.cancel() } }
    LifecycleEventEffect(Lifecycle.Event.ON_STOP) { speech.cancel() }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) { error = null; speech.start() } else error = R.string.voice_permission_denied
    }
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.voice_title)) }, navigationIcon = { ActionIcon(R.drawable.ic_back, R.string.back, action = onBack) }) },
        snackbarHost = { SnackbarHost(snackbar) }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).imePadding().testTag("voice-list"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Text(stringResource(R.string.selected_date, shortDate(vm.date)), style = MaterialTheme.typography.titleMedium) }
            item { Text(stringResource(R.string.voice_hint)) }
            item { Text(stringResource(R.string.voice_privacy), style = MaterialTheme.typography.bodySmall) }
            item {
                if (listening) {
                    Text(stringResource(R.string.voice_listening))
                    Button(onClick = { speech.stop() }) { Text(stringResource(R.string.voice_stop)) }
                    TextButton(onClick = { speech.cancel() }) { Text(stringResource(R.string.voice_cancel)) }
                } else {
                    Button(enabled = !busy, onClick = {
                        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                            error = null; speech.start()
                        } else permission.launch(Manifest.permission.RECORD_AUDIO)
                    }) { Text(stringResource(R.string.voice_start)) }
                }
            }
            error?.let { resource ->
                item {
                    Text(stringResource(resource), color = MaterialTheme.colorScheme.error)
                    if (resource == R.string.voice_permission_denied) TextButton(onClick = {
                        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, ("package:" + context.packageName).toUri()))
                    }) { Text(stringResource(R.string.app_settings)) }
                }
            }
            item {
                OutlinedTextField(raw, vm::rawText, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.voice_raw)) }, minLines = 2, enabled = !listening && !busy)
                TextButton(enabled = raw.isNotBlank() && !listening && !busy, onClick = vm::reparse) { Text(stringResource(R.string.voice_reparse)) }
                Text(stringResource(R.string.voice_reparse_hint), style = MaterialTheme.typography.bodySmall)
            }
            item { Text(stringResource(R.string.voice_preview), style = MaterialTheme.typography.titleMedium) }
            itemsIndexed(lines) { index, line ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        OutlinedTextField(line, { vm.line(index, it) }, Modifier.fillMaxWidth(),
                            label = { Text(stringResource(R.string.voice_task_number, index + 1)) },
                            enabled = !busy && !listening, isError = line.isBlank())
                        TextButton(enabled = !busy && !listening, onClick = { vm.remove(index) }) { Text(stringResource(R.string.delete)) }
                        if (index < lines.lastIndex) TextButton(enabled = !busy && !listening, onClick = { vm.merge(index) }) { Text(stringResource(R.string.voice_merge)) }
                        TextButton(enabled = !busy && !listening, onClick = { splitIndex = index; splitText = line }) { Text(stringResource(R.string.voice_split)) }
                    }
                }
            }
            item { OutlinedButton(enabled = !busy && !listening, onClick = vm::append) { Text(stringResource(R.string.voice_add_row)) } }
            item {
                Button(enabled = lines.isNotEmpty() && lines.all { it.isNotBlank() } && !busy && !listening,
                    onClick = vm::save, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.voice_save, lines.size)) }
            }
        }
    }
    if (splitIndex != null) AlertDialog(
        onDismissRequest = { splitIndex = null },
        title = { Text(stringResource(R.string.voice_split)) },
        text = {
            Column {
                Text(stringResource(R.string.voice_split_hint))
                OutlinedTextField(splitText, { splitText = it }, minLines = 3)
            }
        },
        confirmButton = {
            TextButton(enabled = VoiceParser.splitLines(splitText).size >= 2, onClick = {
                vm.split(splitIndex!!, splitText); splitIndex = null
            }) { Text(stringResource(R.string.voice_split)) }
        },
        dismissButton = { TextButton(onClick = { splitIndex = null }) { Text(stringResource(R.string.cancel)) } }
    )
}
