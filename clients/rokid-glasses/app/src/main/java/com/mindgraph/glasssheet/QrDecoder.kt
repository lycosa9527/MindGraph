package com.mindgraph.glasssheet

import android.util.Log
import androidx.camera.core.ImageProxy
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.ChecksumException
import com.google.zxing.DecodeHintType
import com.google.zxing.FormatException
import com.google.zxing.NotFoundException
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader
import com.google.zxing.qrcode.detector.Detector
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

internal class Luma(val bytes: ByteArray, val width: Int, val height: Int)

internal fun cropLuma(src: Luma, left: Int, top: Int, width: Int, height: Int): Luma? {
    if (width < 1 || height < 1 || src.width < 1 || src.height < 1) return null
    val x0 = left.coerceIn(0, src.width - 1)
    val y0 = top.coerceIn(0, src.height - 1)
    val cropW = width.coerceAtMost(src.width - x0)
    val cropH = height.coerceAtMost(src.height - y0)
    if (cropW < 1 || cropH < 1) return null
    val out = ByteArray(cropW * cropH)
    for (y in 0 until cropH) {
        System.arraycopy(src.bytes, (y0 + y) * src.width + x0, out, y * cropW, cropW)
    }
    return Luma(out, cropW, cropH)
}

internal fun scaleLuma(src: Luma, factor: Int): Luma {
    if (factor <= 1) return src
    val width = src.width * factor
    val height = src.height * factor
    val out = ByteArray(width * height)
    for (y in 0 until height) {
        val fromY = y / factor
        for (x in 0 until width) {
            out[y * width + x] = src.bytes[fromY * src.width + x / factor]
        }
    }
    return Luma(out, width, height)
}

internal fun finderCrop(frameW: Int, frameH: Int, xs: FloatArray, ys: FloatArray): IntArray? {
    if (xs.isEmpty() || xs.size != ys.size) return null
    var minX = xs[0]
    var maxX = xs[0]
    var minY = ys[0]
    var maxY = ys[0]
    for (index in 1 until xs.size) {
        minX = min(minX, xs[index])
        maxX = max(maxX, xs[index])
        minY = min(minY, ys[index])
        maxY = max(maxY, ys[index])
    }
    val span = max(maxX - minX, maxY - minY)
    if (span < 12f) return null
    val pad = span * 0.55f
    val left = (minX - pad).roundToInt().coerceIn(0, frameW - 1)
    val top = (minY - pad).roundToInt().coerceIn(0, frameH - 1)
    val right = (maxX + pad).roundToInt().coerceIn(left + 1, frameW)
    val bottom = (maxY + pad).roundToInt().coerceIn(top + 1, frameH)
    return intArrayOf(left, top, right - left, bottom - top)
}

object QrDecoder {
    private const val PREFIX = "mg://sheet/"
    private const val TAG = "GlassSheet"
    private val hints = mapOf(
        DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE),
        DecodeHintType.TRY_HARDER to true,
    )

    fun read(image: ImageProxy): String? {
        val luma = luma(image) ?: return null
        decode(luma)?.let { return it }
        val points = finders(luma) ?: return null
        val box = finderCrop(luma.width, luma.height, points.first, points.second) ?: return null
        val crop = cropLuma(luma, box[0], box[1], box[2], box[3]) ?: return null
        val factor = zoomFactor(crop.width)
        val zoomed = scaleLuma(crop, factor)
        Log.i(TAG, "qr zoom ${crop.width}x${crop.height} x$factor")
        return decode(zoomed)
    }

    internal fun zoomFactor(cropWidth: Int): Int {
        if (cropWidth <= 0) return 1
        return ((480 + cropWidth - 1) / cropWidth).coerceIn(1, 4)
    }

    private fun luma(image: ImageProxy): Luma? {
        val plane = image.planes.firstOrNull() ?: return null
        val buffer = plane.buffer.duplicate()
        buffer.rewind()
        val width = image.width
        val height = image.height
        val rowStride = plane.rowStride
        val pixelStride = plane.pixelStride.coerceAtLeast(1)
        if (width <= 0 || height <= 0 || rowStride < width) return null
        val packed = ByteArray(width * height)
        val row = ByteArray(rowStride)
        for (y in 0 until height) {
            val read = min(rowStride, buffer.remaining())
            if (read < (width - 1) * pixelStride + 1) return null
            buffer.get(row, 0, read)
            for (x in 0 until width) {
                packed[y * width + x] = row[x * pixelStride]
            }
        }
        return Luma(packed, width, height)
    }

    private fun finders(luma: Luma): Pair<FloatArray, FloatArray>? {
        return try {
            val detected = Detector(source(luma).blackMatrix).detect(hints)
            val points = detected.points
            if (points.size < 3) return null
            Pair(FloatArray(points.size) { points[it].x }, FloatArray(points.size) { points[it].y })
        } catch (_: NotFoundException) {
            null
        } catch (_: FormatException) {
            null
        }
    }

    private fun decode(luma: Luma): String? {
        return try {
            val result = QRCodeReader().decode(source(luma), hints)
            sheetId(result.text)
        } catch (_: NotFoundException) {
            null
        } catch (_: ChecksumException) {
            null
        } catch (_: FormatException) {
            null
        } catch (_: IllegalArgumentException) {
            null
        }
    }

    private fun source(luma: Luma): BinaryBitmap {
        val planar = PlanarYUVLuminanceSource(
            luma.bytes,
            luma.width,
            luma.height,
            0,
            0,
            luma.width,
            luma.height,
            false,
        )
        return BinaryBitmap(HybridBinarizer(planar))
    }

    private fun sheetId(text: String): String? {
        val trimmed = text.trim()
        val id = if (trimmed.startsWith(PREFIX)) trimmed.removePrefix(PREFIX) else trimmed
        val slash = id.indexOf('/')
        val uuid = if (slash < 0) id else id.substring(0, slash)
        val seq = if (slash < 0) "" else id.substring(slash + 1)
        if (uuid.length != 36 || uuid.any { it == '/' }) return null
        if (seq.isNotEmpty() && (seq.length > 4 || seq.any { !it.isDigit() } || seq.toInt() < 1)) return null
        return id
    }
}
