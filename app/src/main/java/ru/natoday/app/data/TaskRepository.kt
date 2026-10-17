package ru.natoday.app.data

import kotlinx.coroutines.flow.Flow
import java.time.Clock
import java.time.Instant
import java.time.LocalDate

interface Tasks {
    fun observeDay(date: LocalDate): Flow<List<Task>>
    suspend fun add(titles: List<String>, date: LocalDate)
    suspend fun rename(id: Long, title: String)
    suspend fun complete(id: Long, completed: Boolean)
    suspend fun move(id: Long, date: LocalDate): Boolean
    suspend fun delete(id: Long): Task?
    suspend fun restore(task: Task)
}

class TaskRepository(private val dao: TaskDao, private val clock: Clock = Clock.systemUTC()) : Tasks {
    override fun observeDay(date: LocalDate) = dao.observeDay(date)
    override suspend fun add(titles: List<String>, date: LocalDate) {
        require(titles.isNotEmpty())
        val cleaned = titles.map { it.trim().also { title -> require(title.isNotEmpty()) } }
        val now = Instant.now(clock)
        dao.insert(cleaned.map { Task(title = it, scheduledDate = date, createdAt = now) })
    }
    override suspend fun rename(id: Long, title: String) {
        require(title.isNotBlank())
        dao.rename(id, title.trim())
    }
    override suspend fun complete(id: Long, completed: Boolean) = dao.complete(id, completed, Instant.now(clock))
    override suspend fun move(id: Long, date: LocalDate) = dao.move(id, date) == 1
    override suspend fun delete(id: Long) = dao.remove(id)
    override suspend fun restore(task: Task) { dao.restore(task) }
}
