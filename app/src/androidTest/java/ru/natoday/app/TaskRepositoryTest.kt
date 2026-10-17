package ru.natoday.app

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import ru.natoday.app.data.*
import java.time.*

class TaskRepositoryTest {
    private lateinit var db: TaskDatabase
    private lateinit var tasks: TaskRepository
    private val today = LocalDate.of(2028, 2, 28)
    private val now = Instant.parse("2028-02-28T20:00:00Z")
    @Before fun setup() {
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), TaskDatabase::class.java).build()
        tasks = TaskRepository(db.tasks(), Clock.fixed(now, ZoneOffset.UTC))
    }
    @After fun teardown() { db.close() }

    @Test fun completionAndUndoKeepIdentityAndCreationTime() = runBlocking {
        tasks.add(listOf("  Дело  "), today)
        val original = tasks.observeDay(today).first().single()
        assertEquals("Дело", original.title)
        tasks.complete(original.id, true)
        val complete = tasks.observeDay(today).first().single()
        assertEquals(now, complete.completedAt)
        assertEquals(original.id, complete.id)
        assertEquals(original.createdAt, complete.createdAt)
        tasks.complete(original.id, true)
        assertEquals(now, tasks.observeDay(today).first().single().completedAt)
        tasks.complete(original.id, false)
        assertNull(tasks.observeDay(today).first().single().completedAt)
    }
    @Test fun moveUpdatesTheSameRowWithoutCompletionOrDuplicates() = runBlocking {
        tasks.add(listOf("Дело"), today)
        val task = tasks.observeDay(today).first().single()
        assertTrue(tasks.move(task.id, today.plusDays(1)))
        assertFalse(tasks.move(task.id, today.plusDays(1)))
        assertTrue(tasks.observeDay(today).first().isEmpty())
        val moved = tasks.observeDay(today.plusDays(1)).first().single()
        assertEquals(task.id, moved.id)
        assertEquals(task.createdAt, moved.createdAt)
        assertNull(moved.completedAt)
    }
    @Test fun renameDeleteAndUndoRestoreOneOriginalRow() = runBlocking {
        tasks.add(listOf("Исходная"), today)
        val task = tasks.observeDay(today).first().single()
        tasks.rename(task.id, "  Исправленная  ")
        val deleted = tasks.delete(task.id)!!
        assertTrue(tasks.observeDay(today).first().isEmpty())
        tasks.restore(deleted)
        tasks.restore(deleted)
        val restored = tasks.observeDay(today).first().single()
        assertEquals(task.id, restored.id)
        assertEquals("Исправленная", restored.title)
    }
    @Test fun rejectsBlankBatchWithoutPartialInsert() = runBlocking {
        try { tasks.add(listOf("Дело", " "), today); fail("Blank task must be rejected") } catch (_: IllegalArgumentException) { }
        assertTrue(tasks.observeDay(today).first().isEmpty())
    }
    @Test fun databaseSurvivesCloseAndReopen() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val name = "persistence-test.db"
        context.deleteDatabase(name)
        val first = Room.databaseBuilder(context, TaskDatabase::class.java, name).build()
        TaskRepository(first.tasks()).add(listOf("Сохранено"), today)
        first.close()
        val second = Room.databaseBuilder(context, TaskDatabase::class.java, name).build()
        try { assertEquals("Сохранено", second.tasks().observeDay(today).first().single().title) }
        finally { second.close(); context.deleteDatabase(name) }
    }
}
