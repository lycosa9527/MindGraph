package com.mindgraph.glasssheet

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Posts one canvas nudge for the wearer token saved when the bind photo succeeded. */
class CanvasRemote(ingestUrl: String) {
    private val url = glassesRemoteUrl(ingestUrl)
    private val client = OkHttpClient.Builder()
        .callTimeout(4, TimeUnit.SECONDS)
        .build()

    fun send(token: String, action: String): RemoteAck {
        if (token.isBlank()) return RemoteAck.NEED_BIND
        val payload = JSONObject().put("token", token).put("action", action).toString()
        val request = Request.Builder()
            .url(url)
            .post(payload.toRequestBody(JSON))
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (!response.isSuccessful) return RemoteAck.FAILED
                display(text)
            }
        } catch (_: IOException) {
            RemoteAck.FAILED
        }
    }

    private fun display(text: String): RemoteAck {
        return try {
            val line = JSONObject(text).optString("display")
            if (line.isBlank()) RemoteAck.FAILED else RemoteAck.Sent(line)
        } catch (_: JSONException) {
            RemoteAck.FAILED
        }
    }

    private companion object {
        val JSON = "application/json; charset=utf-8".toMediaType()
    }
}

sealed class RemoteAck {
    data object NEED_BIND : RemoteAck()
    data object FAILED : RemoteAck()
    data class Sent(val line: String) : RemoteAck()
}
