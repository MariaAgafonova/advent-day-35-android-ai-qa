package ru.natoday.app.ui

import androidx.lifecycle.SavedStateHandle
import ru.natoday.app.data.Tasks
import ru.natoday.app.voice.VoiceParser
import java.time.LocalDate

class VoiceViewModel(tasks: Tasks, val date: LocalDate, private val saved: SavedStateHandle) : TaskActionsViewModel(tasks) {
    val raw = saved.getStateFlow("raw_text", "")
    val lines = saved.getStateFlow("draft_lines", arrayListOf<String>())
    fun rawText(value: String) { saved["raw_text"] = value }
    fun recognized(value: String) { rawText(value); reparse() }
    fun reparse() { saved["draft_lines"] = ArrayList(VoiceParser.split(raw.value)) }
    fun line(index: Int, value: String) { update { it[index] = value } }
    fun remove(index: Int) { update { it.removeAt(index) } }
    fun append() { update { it.add("") } }
    fun merge(index: Int) {
        update { list ->
            if (index < list.lastIndex) {
                list[index] = list[index].trim() + " " + list[index + 1].trim()
                list.removeAt(index + 1)
            }
        }
    }
    fun split(index: Int, text: String) {
        val parts = VoiceParser.splitLines(text)
        if (parts.size < 2) return
        update { list -> list.removeAt(index); list.addAll(index, parts) }
    }
    private fun update(action: (ArrayList<String>) -> Unit) {
        val copy = ArrayList(lines.value)
        action(copy)
        saved["draft_lines"] = copy
    }
    fun save() { add(lines.value, date, notifySaved = true) }
}
