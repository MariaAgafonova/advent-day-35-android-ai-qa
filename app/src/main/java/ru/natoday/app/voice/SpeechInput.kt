package ru.natoday.app.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import ru.natoday.app.R

class SpeechInput(
    private val context: Context,
    private val onText: (String) -> Unit,
    private val onError: (Int) -> Unit,
    private val onListening: (Boolean) -> Unit,
) {
    private var recognizer: SpeechRecognizer? = null
    private var active = false

    fun start() {
        cancel()
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            onError(R.string.voice_unavailable)
            return
        }
        try {
            val speech = SpeechRecognizer.createSpeechRecognizer(context)
            recognizer = speech
            speech.let {
                speech.setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: Bundle?) = Unit
                    override fun onBeginningOfSpeech() = Unit
                    override fun onRmsChanged(rmsdB: Float) = Unit
                    override fun onBufferReceived(buffer: ByteArray?) = Unit
                    override fun onEndOfSpeech() = Unit
                    override fun onPartialResults(partialResults: Bundle?) = Unit
                    override fun onEvent(eventType: Int, params: Bundle?) = Unit
                    override fun onError(error: Int) {
                        if (!active) return
                        finish()
                        onError(errorResource(error))
                    }
                    override fun onResults(results: Bundle?) {
                        if (!active) return
                        val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                        finish()
                        if (text.isBlank()) onError(R.string.voice_no_speech) else onText(text)
                    }
                })
                active = true
                onListening(true)
                speech.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU")
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                })
            }
        } catch (_: SecurityException) {
            finish()
            onError(R.string.voice_permission_denied)
        } catch (_: RuntimeException) {
            finish()
            onError(R.string.voice_failed)
        }
    }
    fun stop() { if (active) recognizer?.stopListening() }
    fun cancel() {
        active = false
        recognizer?.cancel()
        recognizer?.destroy()
        recognizer = null
        onListening(false)
    }
    private fun finish() {
        active = false
        onListening(false)
        recognizer?.destroy()
        recognizer = null
    }
    companion object {
        fun errorResource(error: Int): Int = when (error) {
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> R.string.voice_permission_denied
            SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> R.string.voice_no_speech
            SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> R.string.voice_network
            SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED, SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE -> R.string.voice_language
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> R.string.voice_busy
            else -> R.string.voice_failed
        }
    }
}
