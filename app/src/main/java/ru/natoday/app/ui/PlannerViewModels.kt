package ru.natoday.app.ui

import android.util.Log
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import ru.natoday.app.R
import ru.natoday.app.data.*
import ru.natoday.app.reminders.ReminderScheduler
import java.time.LocalDate
import java.time.LocalTime

sealed interface UiEvent {
    data class Message(val resource: Int) : UiEvent
    data class Deleted(val task: Task) : UiEvent
    data object Saved : UiEvent
}

open class TaskActionsViewModel(protected val tasks: Tasks) : ViewModel() {
    private val eventChannel = Channel<UiEvent>(Channel.BUFFERED)
    val events = eventChannel.receiveAsFlow()
    val busy = MutableStateFlow(false)
    protected fun perform(action: suspend () -> Unit) {
        if (busy.value) return
        busy.value = true
        viewModelScope.launch {
            try { action() }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) {
                Log.e("Planner", "Task operation failed", error)
                eventChannel.send(UiEvent.Message(R.string.storage_error))
            } finally { busy.value = false }
        }
    }
    protected suspend fun emit(event: UiEvent) { eventChannel.send(event) }
    fun complete(task: Task, value: Boolean) = perform { tasks.complete(task.id, value) }
    open fun move(task: Task, date: LocalDate) = perform { tasks.move(task.id, date) }
    fun rename(task: Task, title: String) = perform { tasks.rename(task.id, title) }
    fun delete(task: Task) = perform { tasks.delete(task.id)?.let { emit(UiEvent.Deleted(it)) } }
    fun restore(task: Task) = perform { tasks.restore(task) }
    fun add(titles: List<String>, date: LocalDate, notifySaved: Boolean = false) = perform {
        tasks.add(titles, date)
        if (notifySaved) emit(UiEvent.Saved)
    }
}

data class DayState(val date: LocalDate, val tasks: List<Task> = emptyList(), val loading: Boolean = false, val error: Boolean = false)

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class DayViewModel(tasks: Tasks, private val saved: SavedStateHandle) : TaskActionsViewModel(tasks) {
    private val day = saved.getStateFlow("selected_day", LocalDate.now().toEpochDay())
    private var lastToday = LocalDate.now()
    val state: StateFlow<DayState> = day.flatMapLatest { epoch ->
        val date = LocalDate.ofEpochDay(epoch)
        tasks.observeDay(date).map { DayState(date, it) }
            .onStart { emit(DayState(date, loading = true)) }
            .catch { emit(DayState(date, error = true)) }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DayState(LocalDate.ofEpochDay(day.value), loading = true))
    fun select(date: LocalDate) { saved["selected_day"] = date.toEpochDay() }
    fun refreshToday() {
        val today = LocalDate.now()
        if (day.value == lastToday.toEpochDay()) select(today)
        lastToday = today
    }
}

class ReviewViewModel(tasks: Tasks, val date: LocalDate, private val saved: SavedStateHandle) : TaskActionsViewModel(tasks) {
    val moved = saved.getStateFlow("moved_count", 0)
    val state: StateFlow<DayState> = tasks.observeDay(date).map { DayState(date, it) }
        .catch { emit(DayState(date, error = true)) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), DayState(date, loading = true))
    override fun move(task: Task, date: LocalDate) = perform {
        if (tasks.move(task.id, date)) saved["moved_count"] = moved.value + 1
    }
}

class SettingsViewModel(private val repository: SettingsRepository, private val scheduler: ReminderScheduler) : ViewModel() {
    val settings = repository.settings.map<ReminderSettings, ReminderSettings?> { it }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val error = MutableStateFlow(false)
    val busy = MutableStateFlow(false)
    fun enabled(value: Boolean) = update { scheduler.setEnabled(value) }
    fun time(value: LocalTime) = update { scheduler.setTime(value) }
    private fun update(action: suspend () -> Unit) {
        if (busy.value) return
        busy.value = true
        viewModelScope.launch {
            try { action(); error.value = false }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (e: Exception) { Log.e("Planner", "Settings write failed", e); error.value = true }
            finally { busy.value = false }
        }
    }
}
