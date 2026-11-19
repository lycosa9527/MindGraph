package com.mindgraph.glasssheet

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class SheetUploader {
    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    fun send(sheetId: String, jpeg: ByteArray): String {
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("sheet_uuid", sheetId)
            .addFormDataPart(
                "image",
                "sheet.jpg",
                jpeg.toRequestBody(JPEG),
            )
            .build()
        val request = Request.Builder()
            .url(BuildConfig.INGEST_URL)
            .post(body)
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    return "发送失败 ${response.code}"
                }
                displayLine(text)
            }
        } catch (error: IOException) {
            "发送失败"
        }
    }

    fun endpoint(): String = BuildConfig.INGEST_URL

    fun isDeviceBound(line: String): Boolean = line == BOUND

    fun probeUrl(): String {
        val scheme = BuildConfig.INGEST_URL.substringBefore("://")
        val host = BuildConfig.INGEST_URL.substringAfter("://").substringBefore("/")
        return "$scheme://$host/api/config/features"
    }

    private fun displayLine(text: String): String {
        return try {
            JSONObject(text).optString("display", SENT).ifBlank { SENT }
        } catch (error: JSONException) {
            SENT
        }
    }

    private companion object {
        const val SENT = "学生图示已发送"
        const val BOUND = "智能设备已绑定"
        val JPEG = "image/jpeg".toMediaType()
    }
}
