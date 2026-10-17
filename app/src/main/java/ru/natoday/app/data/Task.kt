package ru.natoday.app.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.TypeConverter
import java.time.Instant
import java.time.LocalDate

@Entity(tableName = "tasks", indices = [Index("scheduledDate")])
data class Task(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val title: String,
    val scheduledDate: LocalDate,
    val createdAt: Instant,
    val completedAt: Instant? = null,
)

class TaskConverters {
    @TypeConverter fun dateToLong(date: LocalDate): Long = date.toEpochDay()
    @TypeConverter fun longToDate(value: Long): LocalDate = LocalDate.ofEpochDay(value)
    @TypeConverter fun instantToLong(instant: Instant?): Long? = instant?.toEpochMilli()
    @TypeConverter fun longToInstant(value: Long?): Instant? = value?.let(Instant::ofEpochMilli)
}
