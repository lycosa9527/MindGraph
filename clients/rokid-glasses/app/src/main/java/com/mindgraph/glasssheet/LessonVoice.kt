package com.mindgraph.glasssheet

import android.content.Context
import android.media.MediaPlayer
import android.net.Uri
import android.speech.tts.TextToSpeech
import java.io.File
import java.io.IOException
import java.util.Locale

/**
 * Plays a slide's saved recording on the glasses.
 * A line with no recording is read aloud instead.
 */
class LessonVoice(context: Context) : TextToSpeech.OnInitListener {
    private val appContext = context.applicationContext
    private var ready = false
    private var player: MediaPlayer? = null
    private val engine = TextToSpeech(appContext, this)

    override fun onInit(status: Int) {
        ready = status == TextToSpeech.SUCCESS
    }

    fun play(line: String, voiceUrl: String, token: String) {
        playRecording(line, ByteArray(0), voiceUrl, token) {}
    }

    /** Plays the saved recording. A missing file is read aloud from the line. */
    fun playRecording(
        line: String,
        audio: ByteArray,
        voiceUrl: String = "",
        token: String = "",
        onStarted: (Long) -> Unit,
    ) {
        if (audio.isEmpty() && filePlaying()) return
        releasePlayer()
        if (ready) engine.stop()
        val file = writeRecording(audio)
        if (file != null && startFile(file, line, onStarted)) return
        if (voiceUrl.isNotBlank() && token.isNotBlank() && startStream(line, voiceUrl, token, onStarted)) return
        if (line.isNotBlank()) {
            speak(line)
            onStarted(0)
        }
    }

    fun speak(line: String) {
        if (!ready || line.isBlank()) return
        val chinese = line.any { it.code > 0x2E80 }
        engine.language = if (chinese) Locale.CHINESE else Locale.US
        engine.speak(line, TextToSpeech.QUEUE_FLUSH, null, "mindglass")
    }

    fun stop() {
        releasePlayer()
        engine.stop()
        engine.shutdown()
    }

    private fun writeRecording(audio: ByteArray): File? {
        if (audio.isEmpty()) return null
        val file = File(appContext.cacheDir, "lesson-voice.mp3")
        return try {
            file.writeBytes(audio)
            file
        } catch (_: IOException) {
            null
        }
    }

    private fun startFile(file: File, line: String, onStarted: (Long) -> Unit): Boolean {
        val created = MediaPlayer()
        player = created
        listen(created, line, onStarted)
        val started = try {
            created.setDataSource(file.absolutePath)
            created.prepareAsync()
            true
        } catch (error: IOException) {
            false
        } catch (error: IllegalArgumentException) {
            false
        } catch (error: IllegalStateException) {
            false
        }
        if (!started) drop(created)
        return started
    }

    private fun startStream(
        line: String,
        voiceUrl: String,
        token: String,
        onStarted: (Long) -> Unit,
    ): Boolean {
        val created = MediaPlayer()
        player = created
        listen(created, line, onStarted)
        val started = try {
            created.setDataSource(appContext, Uri.parse(voiceUrl), mapOf("X-Glasses-Token" to token))
            created.prepareAsync()
            true
        } catch (error: IOException) {
            false
        } catch (error: IllegalArgumentException) {
            false
        } catch (error: IllegalStateException) {
            false
        } catch (error: SecurityException) {
            false
        }
        if (!started) drop(created)
        return started
    }

    private fun listen(created: MediaPlayer, line: String, onStarted: (Long) -> Unit) {
        created.setOnPreparedListener { readyPlayer ->
            readyPlayer.start()
            val duration = readyPlayer.duration.toLong()
            if (duration > 0) onStarted(duration)
        }
        created.setOnCompletionListener { finished ->
            if (player === finished) player = null
            finished.release()
        }
        created.setOnErrorListener { failed, _, _ ->
            if (player === failed) player = null
            failed.release()
            if (line.isNotBlank()) speak(line)
            true
        }
    }

    private fun filePlaying(): Boolean {
        val current = player ?: return false
        return try {
            current.isPlaying
        } catch (_: IllegalStateException) {
            false
        }
    }

    private fun drop(created: MediaPlayer) {
        created.setOnErrorListener(null)
        if (player === created) player = null
        created.release()
    }

    private fun releasePlayer() {
        val current = player ?: return
        player = null
        current.setOnPreparedListener(null)
        current.setOnCompletionListener(null)
        current.setOnErrorListener(null)
        current.reset()
        current.release()
    }
}
