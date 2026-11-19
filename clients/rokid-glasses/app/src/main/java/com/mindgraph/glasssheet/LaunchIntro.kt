package com.mindgraph.glasssheet

import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.ImageView
import android.widget.TextView

/**
 * Opens on the M mark, lets it expand, then types Mind Platform.
 * Lasers cross behind the name while it types. The credit fades in with the first letter.
 */
class LaunchIntro(
    private val splash: View,
    private val mark: ImageView,
    private val word: TextView,
    private val credit: TextView,
    private val lasers: LaunchLasers,
    private val brand: String,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var running = false
    private var typed = 0

    fun play() {
        running = true
        splash.visibility = View.VISIBLE
        splash.alpha = 1f
        mark.visibility = View.VISIBLE
        mark.alpha = 0f
        mark.scaleX = 0.72f
        mark.scaleY = 0.72f
        word.alpha = 0f
        word.text = ""
        credit.alpha = 0f
        mark.animate().alpha(1f).scaleX(1.14f).scaleY(1.14f).setDuration(MARK_IN_MS).withEndAction {
            if (!running) return@withEndAction
            mark.animate().scaleX(1f).scaleY(1f).setDuration(MARK_SETTLE_MS).withEndAction {
                if (!running) return@withEndAction
                revealWord()
            }.start()
        }.start()
    }

    fun finish() {
        running = false
        handler.removeCallbacksAndMessages(null)
        mark.animate().cancel()
        word.animate().cancel()
        credit.animate().cancel()
        lasers.stop()
        dismiss()
    }

    private fun revealWord() {
        mark.animate().alpha(0f).setDuration(CROSSFADE_MS).withEndAction {
            if (!running) return@withEndAction
            mark.visibility = View.INVISIBLE
        }.start()
        typed = 1
        word.text = brand.take(1)
        word.alpha = 0f
        word.animate().alpha(1f).setDuration(CROSSFADE_MS).start()
        credit.animate().alpha(1f).setDuration(CROSSFADE_MS).start()
        lasers.play()
        handler.postDelayed(typeStep, CROSSFADE_MS)
    }

    private val typeStep = object : Runnable {
        override fun run() {
            if (!running) return
            if (typed >= brand.length) {
                handler.postDelayed({ dismiss() }, HOLD_MS)
                return
            }
            typed += 1
            word.text = brand.take(typed)
            handler.postDelayed(this, TYPE_MS)
        }
    }

    private fun dismiss() {
        if (splash.visibility == View.GONE) return
        splash.animate().alpha(0f).setDuration(FADE_MS).withEndAction {
            splash.visibility = View.GONE
        }.start()
    }

    private companion object {
        const val MARK_IN_MS = 460L
        const val MARK_SETTLE_MS = 180L
        const val CROSSFADE_MS = 200L
        const val TYPE_MS = 52L
        const val HOLD_MS = 780L
        const val FADE_MS = 220L
    }
}
