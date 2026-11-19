package com.mindgraph.glasssheet

import android.text.format.DateFormat
import android.widget.TextView
import java.util.Calendar

/** Top-left clock. It paints the minute and wakes again on the next second. */
class HudClock(private val view: TextView) {
    private val tick = object : Runnable {
        override fun run() {
            val now = Calendar.getInstance()
            view.text = formatHudClock(
                now.get(Calendar.HOUR_OF_DAY),
                now.get(Calendar.MINUTE),
                DateFormat.is24HourFormat(view.context),
            )
            view.postDelayed(this, TICK_MS)
        }
    }

    fun start() {
        view.removeCallbacks(tick)
        tick.run()
    }

    fun stop() {
        view.removeCallbacks(tick)
    }

    private companion object {
        const val TICK_MS = 1000L
    }
}
