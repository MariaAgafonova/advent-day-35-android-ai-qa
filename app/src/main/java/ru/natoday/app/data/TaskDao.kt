package ru.natoday.app.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow
import java.time.Instant
import java.time.LocalDate

@Dao
abstract class TaskDao {
    @Query("SELECT * FROM tasks WHERE scheduledDate = :date ORDER BY createdAt, id")
    abstract fun observeDay(date: LocalDate): Flow<List<Task>>

    @Query("SELECT * FROM tasks WHERE id = :id")
    abstract suspend fun find(id: Long): Task?

    @Insert
    abstract suspend fun insert(tasks: List<Task>): List<Long>

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    abstract suspend fun restore(task: Task): Long

    @Query("UPDATE tasks SET title = :title WHERE id = :id")
    abstract suspend fun rename(id: Long, title: String)

    @Query("UPDATE tasks SET completedAt = CASE WHEN :completed THEN COALESCE(completedAt, :now) ELSE NULL END WHERE id = :id")
    abstract suspend fun complete(id: Long, completed: Boolean, now: Instant)

    @Query("UPDATE tasks SET scheduledDate = :date WHERE id = :id AND scheduledDate != :date")
    abstract suspend fun move(id: Long, date: LocalDate): Int

    @Query("DELETE FROM tasks WHERE id = :id")
    abstract suspend fun deleteById(id: Long): Int

    @Transaction
    open suspend fun remove(id: Long): Task? {
        val task = find(id) ?: return null
        return if (deleteById(id) == 1) task else null
    }
}
