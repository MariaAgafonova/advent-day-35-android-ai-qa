package ru.natoday.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.natoday.app.R
import ru.natoday.app.data.Task
import ru.natoday.app.reminders.tomorrowForReview
import java.time.LocalDate

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun DayScreen(vm: DayViewModel, onSettings: () -> Unit, onReview: (LocalDate) -> Unit, onVoice: (LocalDate) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var calendar by rememberSaveable { mutableStateOf(false) }
    var adding by rememberSaveable { mutableStateOf(false) }
    var completedExpanded by rememberSaveable { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val dateDescription = stringResource(R.string.choose_date) + ": " + dateLabel(state.date)
    TaskEvents(vm, snackbar)
    Scaffold(
        topBar = {
            TopAppBar(title = { Text(stringResource(R.string.app_name)) },
                actions = { ActionIcon(R.drawable.ic_settings, R.string.settings, action = onSettings) })
        },
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            Surface(tonalElevation = 2.dp) {
                FlowRow(Modifier.navigationBarsPadding().imePadding().padding(16.dp),
                    maxItemsInEachRow = if (LocalDensity.current.fontScale >= 1.5f) 1 else 2,
                    horizontalArrangement = Arrangement.spacedBy(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { adding = true }, enabled = !busy, modifier = Modifier.weight(1f)) {
                        Icon(painterResource(R.drawable.ic_plus), null)
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.add_task))
                    }
                    OutlinedButton(onClick = { onVoice(state.date) }, enabled = !busy, modifier = Modifier.weight(1f)) {
                        Icon(painterResource(R.drawable.ic_mic), null)
                        Spacer(Modifier.width(6.dp))
                        Text(stringResource(R.string.voice_input))
                    }
                }
            }
        }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Text(stringResource(R.string.day_subtitle), color = MaterialTheme.colorScheme.onSurfaceVariant) }
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    ActionIcon(R.drawable.ic_previous, R.string.previous_day) { vm.select(state.date.minusDays(1)) }
                    OutlinedButton(onClick = { calendar = true }, modifier = Modifier.weight(1f).semantics { contentDescription = dateDescription }) { Text(dateLabel(state.date)) }
                    ActionIcon(R.drawable.ic_next, R.string.next_day) { vm.select(state.date.plusDays(1)) }
                }
                TextButton(onClick = { vm.select(LocalDate.now()) }) { Text(stringResource(R.string.today)) }
            }
            item {
                Text(stringResource(R.string.done_count, state.tasks.count { it.completedAt != null }, state.tasks.size), style = MaterialTheme.typography.titleMedium)
            }
            if (state.loading) item { Text(stringResource(R.string.loading)) }
            if (state.error) item { Text(stringResource(R.string.load_error), color = MaterialTheme.colorScheme.error) }
            if (!state.loading && !state.error && state.tasks.isEmpty()) item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(stringResource(R.string.empty_title), style = MaterialTheme.typography.titleLarge)
                        Text(stringResource(R.string.empty_body))
                    }
                }
            }
            val pending = state.tasks.filter { it.completedAt == null }
            if (pending.isNotEmpty()) item { Text(stringResource(R.string.pending), style = MaterialTheme.typography.titleSmall) }
            items(pending, key = { it.id }) { task -> TaskCard(task, vm, busy) }
            if (state.tasks.isNotEmpty() && pending.isEmpty()) item { Text(stringResource(R.string.all_done)) }
            val completed = state.tasks.filter { it.completedAt != null }
            if (completed.isNotEmpty()) {
                item {
                    TextButton(onClick = { completedExpanded = !completedExpanded }) {
                        Text(stringResource(if (completedExpanded) R.string.completed_collapse else R.string.completed_expand, completed.size))
                    }
                }
                if (completedExpanded) items(completed, key = { it.id }) { task -> TaskCard(task, vm, busy) }
            }
            item { OutlinedButton(onClick = { onReview(state.date) }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.review_title)) } }
        }
    }
    if (calendar) ChooseDate(state.date, { calendar = false }, selectImmediately = true) { vm.select(it); calendar = false }
    if (adding) TaskEditor(null, { adding = false }) { vm.add(listOf(it), state.date); adding = false }
}

@Composable
fun TaskEvents(vm: TaskActionsViewModel, snackbar: SnackbarHostState, onSaved: () -> Unit = {}) {
    val context = LocalContext.current
    val resources by rememberUpdatedState(context.resources)
    val saved by rememberUpdatedState(onSaved)
    LaunchedEffect(vm) {
        vm.events.collect { event ->
            when (event) {
                is UiEvent.Message -> snackbar.showSnackbar(resources.getString(event.resource))
                is UiEvent.Deleted -> {
                    if (snackbar.showSnackbar(resources.getString(R.string.deleted), resources.getString(R.string.undo), duration = SnackbarDuration.Long) == SnackbarResult.ActionPerformed)
                        vm.restore(event.task)
                }
                UiEvent.Saved -> saved()
            }
        }
    }
}

@Composable
fun TaskCard(task: Task, vm: TaskActionsViewModel, busy: Boolean, reviewDate: LocalDate? = null) {
    var menu by remember { mutableStateOf(false) }
    var edit by rememberSaveable(task.id) { mutableStateOf(false) }
    var moving by rememberSaveable(task.id) { mutableStateOf(false) }
    val checkDescription = stringResource(if (task.completedAt == null) R.string.complete_task else R.string.uncomplete_task, task.title)
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow)) {
        Row(Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = task.completedAt != null, onCheckedChange = { vm.complete(task, it) }, enabled = !busy,
                modifier = Modifier.semantics { contentDescription = checkDescription })
            Text(task.title, Modifier.weight(1f).clickable(enabled = !busy && reviewDate == null) { edit = true }.padding(vertical = 12.dp),
                style = MaterialTheme.typography.bodyLarge, textDecoration = if (task.completedAt != null) TextDecoration.LineThrough else null)
            Box {
                IconButton(onClick = { menu = true }, enabled = !busy) {
                    Icon(painterResource(R.drawable.ic_more), stringResource(R.string.task_actions, task.title))
                }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    if (reviewDate == null) DropdownMenuItem(text = { Text(stringResource(R.string.edit)) }, onClick = { menu = false; edit = true })
                    DropdownMenuItem(text = { Text(stringResource(R.string.move)) }, onClick = { menu = false; moving = true })
                    DropdownMenuItem(text = { Text(stringResource(R.string.delete)) }, onClick = { menu = false; vm.delete(task) })
                }
            }
        }
        if (reviewDate != null) {
            Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = { vm.complete(task, true) }, enabled = !busy) { Text(stringResource(R.string.mark_done)) }
                OutlinedButton(onClick = { vm.move(task, tomorrowForReview(reviewDate)) }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.move_tomorrow, shortDate(tomorrowForReview(reviewDate))))
                }
                TextButton(onClick = { moving = true }, enabled = !busy) { Text(stringResource(R.string.other_date)) }
            }
        }
    }
    if (edit) TaskEditor(task.title, { edit = false }) { vm.rename(task, it); edit = false }
    if (moving) ChooseDate(task.scheduledDate, { moving = false }) { vm.move(task, it); moving = false }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReviewScreen(vm: ReviewViewModel, onBack: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val moved by vm.moved.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    TaskEvents(vm, snackbar)
    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.review_title)) },
            navigationIcon = { ActionIcon(R.drawable.ic_back, R.string.back, action = onBack) }) },
        snackbarHost = { SnackbarHost(snackbar) }
    ) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Text(dateLabel(vm.date), style = MaterialTheme.typography.titleLarge) }
            item { Text(stringResource(R.string.review_hint)) }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.review_summary, state.tasks.count { it.completedAt != null }, moved), Modifier.padding(20.dp))
                }
            }
            if (state.loading) item { Text(stringResource(R.string.loading)) }
            if (state.error) item { Text(stringResource(R.string.load_error), color = MaterialTheme.colorScheme.error) }
            val pending = state.tasks.filter { it.completedAt == null }
            if (!state.loading && !state.error && pending.isEmpty()) item { Text(stringResource(R.string.review_done), style = MaterialTheme.typography.titleLarge) }
            items(pending, key = { it.id }) { TaskCard(it, vm, busy, vm.date) }
            item { Text(stringResource(R.string.review_reopen), style = MaterialTheme.typography.bodySmall) }
        }
    }
}
