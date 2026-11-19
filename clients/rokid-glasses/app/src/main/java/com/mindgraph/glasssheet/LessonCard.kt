package com.mindgraph.glasssheet

import android.graphics.Canvas
import android.graphics.Paint
import android.os.Handler
import android.os.Looper
import android.text.SpannableString
import android.text.Spanned
import android.text.style.ReplacementSpan
import android.view.View
import android.view.animation.DecelerateInterpolator
import android.widget.TextView

/**
 * A green box for the spoken line. The cursor blinks, then the line types in.
 */
class LessonCard(
    private val card: View,
    private val line: TextView,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var full = ""
    private var typed = 0
    private var cursorOn = true
    private var active = false
    private var entered = false
    private var generation = 0
    private var stepMs = READ_MS

    fun isActive(): Boolean = active

    fun play(text: String) {
        full = text
        typed = 0
        cursorOn = true
        active = true
        entered = false
        generation += 1
        val ticket = generation
        handler.removeCallbacks(typeStep)
        handler.removeCallbacks(beginTyping)
        handler.removeCallbacks(blinkStep)
        paint()
        card.animate().cancel()
        card.visibility = View.VISIBLE
        card.alpha = 0f
        card.scaleX = 0.94f
        card.scaleY = 0.94f
        card.post {
            if (ticket != generation || !active) return@post
            card.pivotX = card.width / 2f
            card.pivotY = card.height / 2f
            card.animate()
                .alpha(1f)
                .scaleX(1f)
                .scaleY(1f)
                .setDuration(ENTER_MS)
                .setInterpolator(DecelerateInterpolator())
                .withEndAction {
                    if (ticket != generation || !active) return@withEndAction
                    entered = true
                }
                .start()
        }
        stepMs = READ_MS
        handler.postDelayed(blinkStep, BLINK_MS)
        handler.postDelayed(beginTyping, ENTER_MS)
    }

    /** Spread the remaining characters across the recording, a little ahead of the voice. */
    fun followVoice(durationMs: Long) {
        if (!active || durationMs <= 0) return
        val remaining = (LessonLine.count(full) - typed).coerceAtLeast(1)
        val budget = durationMs * 86 / 100
        stepMs = (budget / remaining).coerceIn(42L, 280L)
    }

    fun setSheetVisible(sheet: Boolean) {
        if (!active || !sheet) {
            if (!sheet) card.visibility = View.GONE
            return
        }
        card.visibility = View.VISIBLE
        if (!entered) return
        card.alpha = 1f
        card.scaleX = 1f
        card.scaleY = 1f
    }

    fun clear() {
        active = false
        entered = false
        full = ""
        typed = 0
        handler.removeCallbacksAndMessages(null)
        card.animate().cancel()
        card.visibility = View.GONE
        line.text = ""
    }

    private val beginTyping = Runnable {
        if (!active) return@Runnable
        handler.post(typeStep)
    }

    private val typeStep = object : Runnable {
        override fun run() {
            if (!active || typed >= LessonLine.count(full)) return
            typed += 1
            paint()
            if (typed < LessonLine.count(full)) handler.postDelayed(this, stepMs)
        }
    }

    private val blinkStep = object : Runnable {
        override fun run() {
            if (!active) return
            cursorOn = !cursorOn
            paint()
            handler.postDelayed(this, BLINK_MS)
        }
    }

    private fun paint() {
        val body = LessonLine.typed(full, typed)
        val shown = SpannableString("$body ")
        shown.setSpan(
            CaretSpan(cursorOn, CARET),
            body.length,
            shown.length,
            Spanned.SPAN_EXCLUSIVE_EXCLUSIVE,
        )
        line.text = shown
    }

    private class CaretSpan(
        private val on: Boolean,
        private val color: Int,
    ) : ReplacementSpan() {
        override fun getSize(
            paint: Paint,
            text: CharSequence,
            start: Int,
            end: Int,
            fm: Paint.FontMetricsInt?,
        ): Int = caretWidth(paint)

        override fun draw(
            canvas: Canvas,
            text: CharSequence,
            start: Int,
            end: Int,
            x: Float,
            top: Int,
            y: Int,
            bottom: Int,
            paint: Paint,
        ) {
            if (!on) return
            val width = caretWidth(paint).toFloat()
            val ascent = paint.fontMetrics.ascent
            val descent = paint.fontMetrics.descent
            val saved = paint.color
            paint.color = color
            canvas.drawRoundRect(x, y + ascent, x + width, y + descent, width / 2f, width / 2f, paint)
            paint.color = saved
        }

        private fun caretWidth(paint: Paint): Int = (paint.textSize * 0.16f).toInt().coerceAtLeast(4)
    }

    private companion object {
        const val ENTER_MS = 280L
        const val READ_MS = 140L
        const val BLINK_MS = 530L
        const val CARET = 0xFF3DDC84.toInt()
    }
}
