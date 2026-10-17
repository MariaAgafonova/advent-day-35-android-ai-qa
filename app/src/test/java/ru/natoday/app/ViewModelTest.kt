package ru.natoday.app

import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import ru.natoday.app.data.*
import ru.natoday.app.ui.*
import java.time.*

@OptIn(ExperimentalCoroutinesApi::class)
class ViewModelTest {
    private val dispatcher = UnconfinedTestDispatcher()
    @Before fun before() { Dispatchers.setMain(dispatcher) }
    @After fun after() { Dispatchers.resetMain() }

    @Test fun reviewCountsOnlySuccessfulTransfersAndPreservesSession() = runTest {
        val repository = MemoryTasks()
        val date = LocalDate.of(2026, 12, 31)
        repository.add(listOf("Дело"), date)
        val task = repository.values.value.single()
        val saved = SavedStateHandle()
        val vm = ReviewViewModel(repository, date, saved)
        vm.move(task, date)
        assertEquals(0, vm.moved.value)
        vm.move(task, date.plusDays(1))
        vm.move(task, date.plusDays(1))
        assertEquals(1, vm.moved.value)
        assertEquals(1, ReviewViewModel(repository, date, saved).moved.value)
        assertEquals(0, ReviewViewModel(repository, date, SavedStateHandle()).moved.value)
        assertNull(repository.values.value.single().completedAt)
    }
    @Test fun voicePreviewEditingMergingSplittingAndDateArePreserved() = runTest {
        val repository = MemoryTasks()
        val future = LocalDate.of(2028, 2, 29)
        val vm = VoiceViewModel(repository, future, SavedStateHandle())
        vm.recognized("Купить хлеб и молоко новая задача Позвонить")
        assertEquals(2, vm.lines.value.size)
        vm.merge(0)
        assertEquals(1, vm.lines.value.size)
        vm.split(0, "Купить хлеб и молоко\nПозвонить")
        vm.line(1, "Позвонить маме")
        vm.append()
        vm.line(2, "Удалить")
        vm.remove(2)
        vm.save()
        assertEquals(listOf("Купить хлеб и молоко", "Позвонить маме"), repository.values.value.map { it.title })
        assertTrue(repository.values.value.all { it.scheduledDate == future })
    }
    private class MemoryTasks : Tasks {
        val values = MutableStateFlow<List<Task>>(emptyList())
        override fun observeDay(date: LocalDate) = values.map { tasks -> tasks.filter { it.scheduledDate == date } }
        override suspend fun add(titles: List<String>, date: LocalDate) {
            values.value += titles.mapIndexed { index, title -> Task(values.value.size + index + 1L, title, date, Instant.EPOCH) }
        }
        override suspend fun rename(id: Long, title: String) { values.value = values.value.map { if (it.id == id) it.copy(title = title) else it } }
        override suspend fun complete(id: Long, completed: Boolean) {
            values.value = values.value.map { if (it.id == id) it.copy(completedAt = if (completed) Instant.EPOCH else null) else it }
        }
        override suspend fun move(id: Long, date: LocalDate): Boolean {
            if (values.value.none { it.id == id && it.scheduledDate != date }) return false
            values.value = values.value.map { if (it.id == id) it.copy(scheduledDate = date) else it }
            return true
        }
        override suspend fun delete(id: Long): Task? {
            val task = values.value.find { it.id == id }
            values.value = values.value.filterNot { it.id == id }
            return task
        }
        override suspend fun restore(task: Task) { if (values.value.none { it.id == task.id }) values.value += task }
    }
}
