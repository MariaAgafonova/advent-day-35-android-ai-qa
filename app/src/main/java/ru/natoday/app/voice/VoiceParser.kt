package ru.natoday.app.voice

object VoiceParser {
    private val separator = Regex("(?iu)(?<![а-яёa-z])новая\\s+задача(?![а-яёa-z])")
    fun split(text: String): List<String> = text.split(separator)
        .map { it.trim().trim(',', '.', ';', ':', '!', '?').trim() }
        .filter { it.isNotEmpty() }

    fun splitLines(text: String): List<String> = text.lines().flatMap(::split)
}
