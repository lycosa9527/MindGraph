package com.mindgraph.glasssheet

import android.content.Context
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Whether the server answers, and the wearer token saved when a bind photo
 * has already succeeded on this pair of glasses.
 */
class StandbyStatus(
    context: Context,
    private val uploader: SheetUploader,
) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val client = OkHttpClient.Builder()
        .callTimeout(2, TimeUnit.SECONDS)
        .build()

    fun wearerToken(): String = prefs.getString(KEY_TOKEN, "").orEmpty()

    fun rememberWearer(sheetId: String) {
        val token = sheetId.substringBefore("/").trim()
        if (token.length != 36) return
        prefs.edit().putString(KEY_TOKEN, token).apply()
    }

    fun clearWearer() {
        prefs.edit().remove(KEY_TOKEN).apply()
    }

    fun online(): Boolean {
        val request = Request.Builder().url(uploader.probeUrl()).get().build()
        return try {
            client.newCall(request).execute().use { true }
        } catch (_: IOException) {
            false
        }
    }

    private companion object {
        const val PREFS = "glasssheet"
        const val KEY_TOKEN = "wearer"
    }
}
