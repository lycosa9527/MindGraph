package com.mindgraph.glasssheet

/**
 * Temple-pad navigation for the glasses modes, plus the launch word and clock text.
 * The glasses open on the course and follow it as soon as the teacher starts.
 * Canvas mode is a remote for the open diagram.
 * Settings binds, unbinds, or leaves back to the glasses home.
 */
enum class GlassMode { COURSE, CANVAS, SETTINGS }

enum class GlassSetting { BIND, UNBIND, EXIT }

enum class NavKey { LEFT, RIGHT, UP, DOWN, CONFIRM }

enum class RemoteAction(val wire: String) {
    PAN_UP("pan_up"),
    PAN_LEFT("pan_left"),
    FIT("fit"),
    PAN_RIGHT("pan_right"),
    ZOOM_OUT("zoom_out"),
    PAN_DOWN("pan_down"),
    ZOOM_IN("zoom_in"),
}

class RemotePad {
    var row: Int = 1
        private set
    var col: Int = 1
        private set

    fun current(): RemoteAction = cell(row, col) ?: RemoteAction.FIT

    fun center() {
        row = 1
        col = 1
    }

    fun focus(action: RemoteAction) {
        for (nextRow in 0..2) {
            for (nextCol in 0..2) {
                if (cell(nextRow, nextCol) == action) {
                    row = nextRow
                    col = nextCol
                    return
                }
            }
        }
    }

    fun move(dRow: Int, dCol: Int): Boolean {
        val targetRow = (row + dRow).coerceIn(0, 2)
        val targetCol = (col + dCol).coerceIn(0, 2)
        if (targetRow == row && targetCol == col) return false
        val resolved = resolve(targetRow, targetCol, dRow) ?: return false
        row = resolved.first
        col = resolved.second
        return true
    }

    private fun resolve(targetRow: Int, targetCol: Int, dRow: Int): Pair<Int, Int>? {
        if (cell(targetRow, targetCol) != null) return targetRow to targetCol
        if (dRow != 0 && cell(targetRow, 1) != null) return targetRow to 1
        return null
    }

    private fun cell(atRow: Int, atCol: Int): RemoteAction? = when (atRow to atCol) {
        0 to 1 -> RemoteAction.PAN_UP
        1 to 0 -> RemoteAction.PAN_LEFT
        1 to 1 -> RemoteAction.FIT
        1 to 2 -> RemoteAction.PAN_RIGHT
        2 to 0 -> RemoteAction.ZOOM_OUT
        2 to 1 -> RemoteAction.PAN_DOWN
        2 to 2 -> RemoteAction.ZOOM_IN
        else -> null
    }
}

class GlassNav {
    var mode: GlassMode = GlassMode.COURSE
        private set
    var onBar: Boolean = true
        private set
    var setting: GlassSetting = GlassSetting.BIND
        private set
    var slide: Int = 0
        private set
    val pad = RemotePad()

    fun onKey(key: NavKey): RemoteAction? = when {
        onBar || mode == GlassMode.COURSE -> onBar(key)
        mode == GlassMode.SETTINGS -> {
            onSetting(key)
            null
        }
        else -> onPad(key)
    }

    fun showCourse() {
        mode = GlassMode.COURSE
        onBar = true
    }

    fun showCanvas() {
        mode = GlassMode.CANVAS
        onBar = false
        pad.center()
    }

    fun showSettings() {
        mode = GlassMode.SETTINGS
        onBar = false
        setting = GlassSetting.BIND
    }

    fun focus(action: RemoteAction) {
        mode = GlassMode.CANVAS
        onBar = false
        pad.focus(action)
    }

    fun focus(setting: GlassSetting) {
        mode = GlassMode.SETTINGS
        onBar = false
        this.setting = setting
    }

    fun showBar() {
        onBar = true
    }

    fun takeSlide(): Int {
        val moved = slide
        slide = 0
        return moved
    }

    fun neighbor(delta: Int): GlassMode? = BAR.getOrNull(BAR.indexOf(mode) + delta)

    private fun onBar(key: NavKey): RemoteAction? {
        when (key) {
            NavKey.LEFT -> shift(-1)
            NavKey.RIGHT -> shift(1)
            NavKey.CONFIRM -> enter()
            NavKey.DOWN, NavKey.UP -> Unit
        }
        return null
    }

    private fun shift(delta: Int) {
        val index = BAR.indexOf(mode) + delta
        if (index !in BAR.indices) return
        mode = BAR[index]
        onBar = true
        slide = delta
    }

    private fun enter() {
        when (mode) {
            GlassMode.COURSE -> Unit
            GlassMode.CANVAS -> showCanvas()
            GlassMode.SETTINGS -> showSettings()
        }
    }

    private fun onSetting(key: NavKey) {
        when (key) {
            NavKey.UP -> if (!moveSetting(-1)) onBar = true
            NavKey.DOWN -> moveSetting(1)
            else -> Unit
        }
    }

    private fun moveSetting(delta: Int): Boolean {
        val next = setting.ordinal + delta
        if (next !in GlassSetting.entries.indices) return false
        setting = GlassSetting.entries[next]
        return true
    }

    private fun onPad(key: NavKey): RemoteAction? = when (key) {
        NavKey.LEFT -> {
            pad.move(0, -1)
            null
        }
        NavKey.RIGHT -> {
            pad.move(0, 1)
            null
        }
        NavKey.UP -> {
            if (!pad.move(-1, 0)) onBar = true
            null
        }
        NavKey.DOWN -> {
            pad.move(1, 0)
            null
        }
        NavKey.CONFIRM -> pad.current()
    }

    private companion object {
        val BAR = listOf(GlassMode.COURSE, GlassMode.CANVAS, GlassMode.SETTINGS)
    }
}

object MindWordmark {
    const val FULL = "Mind Platform"

    fun textAt(count: Int): String = FULL.take(count.coerceIn(0, FULL.length))
}

fun formatHudClock(hourOfDay: Int, minute: Int, is24Hour: Boolean): String {
    val hour = if (is24Hour) {
        hourOfDay.coerceIn(0, 23)
    } else {
        val wrapped = hourOfDay.coerceIn(0, 23) % 12
        if (wrapped == 0) 12 else wrapped
    }
    return "%d:%02d".format(hour, minute.coerceIn(0, 59))
}

fun glassesRemoteUrl(ingestUrl: String): String {
    val scheme = ingestUrl.substringBefore("://", "http")
    val host = ingestUrl.substringAfter("://", ingestUrl).substringBefore("/")
    return "$scheme://$host/api/learning-space/glasses/remote"
}

fun glassesPlayUrl(ingestUrl: String): String {
    val scheme = ingestUrl.substringBefore("://", "http")
    val host = ingestUrl.substringAfter("://", ingestUrl).substringBefore("/")
    return "$scheme://$host/api/learning-space/glasses/play"
}
