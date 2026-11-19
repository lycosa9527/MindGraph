package com.mindgraph.glasssheet

import android.content.Context
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import android.util.AttributeSet
import android.view.View
import kotlin.math.sin

/**
 * Laser streaks and sparks behind the Mind Platform wordmark.
 * Each streak crosses once while the name types in.
 */
class LaunchLasers @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {
    private val glow = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val core = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeWidth = 2.2f
        color = CORE
    }
    private val spark = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = SPARK }
    private var startedAt = 0L
    private var running = false

    fun play() {
        running = true
        startedAt = System.nanoTime()
        invalidate()
    }

    fun stop() {
        running = false
    }

    override fun onDraw(canvas: Canvas) {
        if (!running || width == 0 || height == 0) return
        val elapsed = (System.nanoTime() - startedAt) / 1_000_000_000f
        for (beam in BEAMS) drawBeam(canvas, beam, elapsed)
        drawSparks(canvas, elapsed)
        if (running) postInvalidateOnAnimation()
    }

    private fun drawBeam(canvas: Canvas, beam: Beam, elapsed: Float) {
        val travel = (elapsed - beam.delay) / beam.duration
        if (travel <= 0f || travel >= 1f) return
        val eased = travel * travel * (3f - 2f * travel)
        val tail = width * 0.42f
        val head = if (beam.forward) {
            -tail + (width + tail * 2f) * eased
        } else {
            width + tail - (width + tail * 2f) * eased
        }
        val y = height * beam.band + (head - width / 2f) * beam.slope
        val from = if (beam.forward) head - tail else head + tail
        val shader = LinearGradient(
            from,
            y,
            head,
            y,
            intArrayOf(0x00000000, beam.color, CORE),
            floatArrayOf(0f, 0.78f, 1f),
            Shader.TileMode.CLAMP,
        )
        glow.shader = shader
        glow.strokeWidth = beam.glow
        glow.alpha = (210 * beamFade(travel)).toInt()
        canvas.drawLine(from, y, head, y, glow)
        core.alpha = (255 * beamFade(travel)).toInt()
        canvas.drawLine(head - if (beam.forward) 18f else -18f, y, head, y, core)
        spark.alpha = core.alpha
        canvas.drawCircle(head, y, 2.4f, spark)
    }

    private fun drawSparks(canvas: Canvas, elapsed: Float) {
        val count = SPARK_X.size
        for (index in 0 until count) {
            val wave = sin(elapsed * 7.5 + index * 1.37).toFloat()
            if (wave < 0.35f) continue
            val alpha = ((wave - 0.35f) / 0.65f * 220f).toInt()
            spark.alpha = alpha
            val x = width * SPARK_X[index]
            val y = height * SPARK_Y[index]
            canvas.drawCircle(x, y, if (index % 3 == 0) 1.8f else 1.2f, spark)
        }
    }

    private fun beamFade(travel: Float): Float {
        val edge = 0.12f
        val into = (travel / edge).coerceAtMost(1f)
        val out = ((1f - travel) / edge).coerceAtMost(1f)
        return into * out
    }

    private class Beam(
        val delay: Float,
        val duration: Float,
        val band: Float,
        val slope: Float,
        val glow: Float,
        val forward: Boolean,
        val color: Int,
    )

    private companion object {
        const val CORE = 0xFFF4FFF9.toInt()
        const val SPARK = 0xFF7AF0FF.toInt()
        const val MINT = 0xFF3DDC84.toInt()
        const val CYAN = 0xFF5CE1FF.toInt()
        val BEAMS = arrayOf(
            Beam(0f, 0.82f, 0.46f, -0.04f, 8f, true, MINT),
            Beam(0.16f, 0.7f, 0.54f, 0.035f, 6f, true, CYAN),
            Beam(0.28f, 0.9f, 0.5f, 0.02f, 5f, false, MINT),
        )
        val SPARK_X = floatArrayOf(
            0.12f, 0.22f, 0.31f, 0.4f, 0.48f, 0.57f, 0.66f, 0.74f, 0.83f, 0.9f,
            0.18f, 0.36f, 0.52f, 0.7f, 0.86f,
        )
        val SPARK_Y = floatArrayOf(
            0.34f, 0.62f, 0.4f, 0.68f, 0.32f, 0.6f, 0.38f, 0.66f, 0.36f, 0.58f,
            0.48f, 0.44f, 0.7f, 0.3f, 0.52f,
        )
    }
}
