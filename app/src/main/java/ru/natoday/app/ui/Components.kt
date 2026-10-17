package ru.natoday.app.ui

import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import ru.natoday.app.R
import java.time.*
import java.time.format.DateTimeFormatter
import java.util.Locale

fun dateLabel(date: LocalDate): String = date.format(DateTimeFormatter.ofPattern("d MMMM yyyy, EEEE", Locale.forLanguageTag("ru")))
fun shortDate(date: LocalDate): String = date.format(DateTimeFormatter.ofPattern("d MMMM yyyy", Locale.forLanguageTag("ru")))

@Composable
fun ActionIcon(@DrawableRes image: Int, @StringRes description: Int, enabled: Boolean = true, action: () -> Unit) {
    IconButton(onClick = action, enabled = enabled) {
        Icon(painterResource(image), stringResource(description))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChooseDate(initial: LocalDate, onDismiss: () -> Unit, selectImmediately: Boolean = false, onSelected: (LocalDate) -> Unit) {
    val initialMillis = initial.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
    val picker = rememberDatePickerState(
        // Leave selection empty so opening the calendar does not trigger navigation,
        // and tapping the day already being viewed still counts as a selection.
        initialSelectedDateMillis = if (selectImmediately) null else initialMillis,
        initialDisplayedMonthMillis = initialMillis,
        yearRange = 1..9999,
    )
    if (selectImmediately) {
        LaunchedEffect(picker.selectedDateMillis) {
            picker.selectedDateMillis?.let { onSelected(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate()) }
        }
    }
    DatePickerDialog(onDismissRequest = onDismiss,
        confirmButton = {
            if (!selectImmediately) TextButton(enabled = picker.selectedDateMillis != null, onClick = {
                picker.selectedDateMillis?.let { onSelected(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate()) }
            }) { Text(stringResource(R.string.save)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } }
    ) { DatePicker(state = picker, showModeToggle = !selectImmediately) }
}

@Composable
fun TaskEditor(initial: String?, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var text by rememberSaveable { mutableStateOf(initial.orEmpty()) }
    var attempted by rememberSaveable { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(if (initial == null) R.string.add_task else R.string.edit_task)) },
        text = {
            OutlinedTextField(value = text, onValueChange = { text = it }, label = { Text(stringResource(R.string.task_title)) },
                isError = attempted && text.isBlank(), minLines = 2, maxLines = 6,
                supportingText = { if (attempted && text.isBlank()) Text(stringResource(R.string.empty_title_error)) })
        },
        confirmButton = {
            TextButton(onClick = { attempted = true; if (text.isNotBlank()) onSave(text.trim()) }) { Text(stringResource(R.string.save)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
    )
}

@Composable
fun ChooseTime(initial: LocalTime, onDismiss: () -> Unit, onSelected: (LocalTime) -> Unit) {
    var hour by rememberSaveable { mutableStateOf("%02d".format(initial.hour)) }
    var minute by rememberSaveable { mutableStateOf("%02d".format(initial.minute)) }
    val h = hour.toIntOrNull()
    val m = minute.toIntOrNull()
    val valid = h != null && m != null && h in 0..23 && m in 0..59
    AlertDialog(onDismissRequest = onDismiss, title = { Text(stringResource(R.string.time_picker)) },
        text = {
            Column {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(hour, { if (it.length <= 2) hour = it }, Modifier.weight(1f),
                        label = { Text(stringResource(R.string.hour)) }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                    OutlinedTextField(minute, { if (it.length <= 2) minute = it }, Modifier.weight(1f),
                        label = { Text(stringResource(R.string.minute)) }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                }
                if (!valid) Text(stringResource(R.string.time_invalid), color = MaterialTheme.colorScheme.error)
            }
        },
        confirmButton = { TextButton(enabled = valid, onClick = { onSelected(LocalTime.of(h!!, m!!)) }) { Text(stringResource(R.string.save)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.cancel)) } },
    )
}
