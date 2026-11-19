package com.mindgraph.glasssheet

import android.graphics.PorterDuff
import android.graphics.PorterDuffColorFilter
import android.view.View
import android.widget.ImageView
import android.widget.TextView

/**
 * One app name in the center. Sliding left or right brings the next name in.
 * A tap confirms the centered app.
 */
class ModeSlider(
    private val row: View,
    private val previous: TextView,
    private val currentGroup: View,
    private val icon: ImageView,
    private val current: TextView,
    private val following: TextView,
) {
    private var shown: GlassMode? = null

    fun wire(onSlide: (Int) -> Unit, onConfirm: () -> Unit) {
        previous.setOnClickListener { onSlide(-1) }
        following.setOnClickListener { onSlide(1) }
        currentGroup.setOnClickListener { onConfirm() }
    }

    fun render(
        mode: GlassMode,
        previousMode: GlassMode?,
        nextMode: GlassMode?,
        onBar: Boolean,
        direction: Int,
    ) {
        previous.text = title(previousMode)
        previous.visibility = if (previous.text.isEmpty()) View.INVISIBLE else View.VISIBLE
        following.text = title(nextMode)
        following.visibility = if (following.text.isEmpty()) View.INVISIBLE else View.VISIBLE
        current.text = title(mode)
        icon.contentDescription = current.text
        icon.setImageResource(iconOf(mode))
        icon.drawable?.mutate()
        val color = if (onBar) ON else DIM
        current.setTextColor(color)
        icon.colorFilter = PorterDuffColorFilter(color, PorterDuff.Mode.SRC_IN)
        row.alpha = if (onBar) 1f else 0.72f
        if (direction != 0 && shown != null) {
            row.animate().cancel()
            row.translationX = TRAVEL * direction
            row.animate().translationX(0f).setDuration(SLIDE_MS).start()
        }
        shown = mode
    }

    private fun title(mode: GlassMode?): String {
        val name = mode ?: return ""
        return row.context.getString(
            when (name) {
                GlassMode.COURSE -> R.string.mode_course
                GlassMode.CANVAS -> R.string.mode_canvas
                GlassMode.SETTINGS -> R.string.mode_settings
            },
        )
    }

    private fun iconOf(mode: GlassMode): Int = when (mode) {
        GlassMode.COURSE -> R.drawable.ic_mode_course
        GlassMode.CANVAS -> R.drawable.ic_mode_canvas
        GlassMode.SETTINGS -> R.drawable.ic_mode_settings
    }

    private companion object {
        const val SLIDE_MS = 160L
        const val TRAVEL = 72f
        const val ON = 0xFFFFFFFF.toInt()
        const val DIM = 0x99FFFFFF.toInt()
    }
}
