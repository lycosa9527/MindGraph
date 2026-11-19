package com.mindgraph.glasssheet

/**
 * Fires once when the same sheet id stays readable, then ignores it until the
 * code has been out of frame long enough to count as looking away.
 */
class SheetGate(
    private val stableFrames: Int = 3,
    private val awayMillis: Long = 800L,
) {
    private var streakId: String? = null
    private var streak: Int = 0
    private var latchedId: String? = null
    private var lastSeenMs: Long = 0L

    fun onFrame(sheetId: String?, nowMs: Long): Boolean {
        if (sheetId == null) {
            if (latchedId != null && nowMs - lastSeenMs >= awayMillis) {
                latchedId = null
            }
            streak = 0
            streakId = null
            return false
        }
        lastSeenMs = nowMs
        if (sheetId == latchedId) {
            streak = 0
            streakId = null
            return false
        }
        if (sheetId == streakId) {
            streak += 1
        } else {
            streakId = sheetId
            streak = 1
        }
        if (streak < stableFrames) {
            return false
        }
        latchedId = sheetId
        streak = 0
        streakId = null
        return true
    }

    /** A failed upload must be able to fire again without looking away. */
    fun forget() {
        latchedId = null
        streak = 0
        streakId = null
    }
}
