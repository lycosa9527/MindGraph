package com.mindgraph.glasssheet

import android.util.Base64
import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/** Follows the slide the computer is showing, and asks it to advance on a tap. */
class LessonPlay(ingestUrl: String) {
    private val url = glassesPlayUrl(ingestUrl)
    private val origin = url.substringBefore("/api/")
    private val client = OkHttpClient.Builder()
        .callTimeout(20, TimeUnit.SECONDS)
        .build()
    private val streamClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .callTimeout(0, TimeUnit.MILLISECONDS)
        .build()
    private val watching = AtomicBoolean(false)
    private val generation = AtomicInteger()
    private var streamCall: Call? = null

    fun fetchFollow(token: String, since: Int): FollowSlide? {
        if (token.isBlank()) return null
        val request = Request.Builder()
            .url("$origin/api/learning-space/glasses/follow?since=$since")
            .header("X-Glasses-Token", token)
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                if (response.code == 204 || !response.isSuccessful) return null
                parseFollow(response.body?.string().orEmpty())
            }
        } catch (_: IOException) {
            null
        }
    }

    fun askNext(token: String): NextAck {
        if (token.isBlank()) return NextAck.NeedBind
        val body = JSONObject().put("token", token).put("payload", "next").toString()
        val request = Request.Builder()
            .url(url)
            .post(body.toRequestBody(JSON))
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (!response.isSuccessful) return NextAck.Failed
                val json = JSONObject(text)
                if (json.optBoolean("accepted")) return NextAck.Accepted
                if (json.optString("notice") == "over") NextAck.Over else NextAck.Idle
            }
        } catch (_: IOException) {
            NextAck.Failed
        } catch (_: JSONException) {
            NextAck.Failed
        }
    }

    /**
     * Hold the course stream. A follow frame fetches that slide once.
     * A voice frame fetches the recording the editor just sent.
     */
    fun watch(token: String, onFollow: (FollowSlide) -> Unit, onVoice: (ByteArray) -> Unit) {
        stop()
        if (token.isBlank()) return
        val mine = generation.incrementAndGet()
        watching.set(true)
        Thread {
            while (watching.get() && generation.get() == mine) {
                readStream(token, onFollow, onVoice)
                if (!watching.get() || generation.get() != mine) return@Thread
                try {
                    Thread.sleep(RECONNECT_MS)
                } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                    return@Thread
                }
            }
        }.start()
    }

    fun stop() {
        generation.incrementAndGet()
        watching.set(false)
        streamCall?.cancel()
        streamCall = null
    }

    private fun readStream(
        token: String,
        onFollow: (FollowSlide) -> Unit,
        onVoice: (ByteArray) -> Unit,
    ) {
        val request = Request.Builder()
            .url("$origin/api/learning-space/glasses/device-events")
            .header("X-Glasses-Token", token)
            .header("Accept", "text/event-stream")
            .build()
        val call = streamClient.newCall(request)
        streamCall = call
        try {
            call.execute().use { response ->
                if (!response.isSuccessful) return
                deliverFollow(token, onFollow)
                val source = response.body?.source() ?: return
                var event = ""
                while (watching.get()) {
                    val line = source.readUtf8Line() ?: break
                    if (line.startsWith("event:")) {
                        event = line.substringAfter(":").trim()
                    } else if (line.isEmpty() && event.isNotEmpty()) {
                        dispatch(token, event, onFollow, onVoice)
                        event = ""
                    }
                }
            }
        } catch (_: IOException) {
            return
        }
    }

    private fun dispatch(
        token: String,
        event: String,
        onFollow: (FollowSlide) -> Unit,
        onVoice: (ByteArray) -> Unit,
    ) {
        when (event) {
            "follow" -> deliverFollow(token, onFollow)
            "voice" -> onVoice(fetchVoiceCue(token))
        }
    }

    private fun deliverFollow(token: String, onFollow: (FollowSlide) -> Unit) {
        val slide = fetchFollow(token, 0)
        if (slide != null) onFollow(slide)
    }

    /** The recording the editor just sent, or empty when the glasses have nothing new. */
    fun fetchVoiceCue(token: String): ByteArray {
        if (token.isBlank()) return ByteArray(0)
        val request = Request.Builder()
            .url("$origin/api/learning-space/glasses/voice/cue")
            .header("X-Glasses-Token", token)
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return ByteArray(0)
                response.body?.bytes() ?: ByteArray(0)
            }
        } catch (_: IOException) {
            ByteArray(0)
        }
    }

    private fun parseFollow(text: String): FollowSlide? {
        return try {
            val json = JSONObject(text)
            FollowSlide(
                seq = json.optInt("seq"),
                active = json.optBoolean("active"),
                done = json.optBoolean("done"),
                line = json.optString("display"),
                audio = decodeRecording(json.optString("voice_b64")),
            )
        } catch (_: JSONException) {
            null
        }
    }

    private companion object {
        val JSON = "application/json; charset=utf-8".toMediaType()
        const val RECONNECT_MS = 1000L

        fun decodeRecording(encoded: String): ByteArray {
            if (encoded.isBlank()) return ByteArray(0)
            return try {
                Base64.decode(encoded, Base64.DEFAULT)
            } catch (_: IllegalArgumentException) {
                ByteArray(0)
            }
        }
    }
}

data class FollowSlide(
    val seq: Int,
    val active: Boolean,
    val done: Boolean,
    val line: String,
    val audio: ByteArray,
)

sealed class NextAck {
    data object NeedBind : NextAck()
    data object Failed : NextAck()
    data object Accepted : NextAck()
    data object Idle : NextAck()
    data object Over : NextAck()
}

/** A short confirm asks for the next slide. Holding past that is not a tap. */
class LessonTap {
    private var armed = false
    private var held = false

    fun press() {
        armed = true
        held = false
    }

    /** True once, when the hold becomes leave-home. */
    fun hold(): Boolean {
        if (!armed || held) return false
        held = true
        return true
    }

    /** True when the finger came up before the hold. */
    fun release(): Boolean {
        val tap = armed && !held
        armed = false
        held = false
        return tap
    }

    fun cancel() {
        armed = false
        held = false
    }
}
