package com.mindgraph.glasssheet

/** How much of a spoken line is on screen, counted in characters the reader sees. */
object LessonLine {
    fun count(text: String): Int = text.codePointCount(0, text.length)

    fun typed(text: String, count: Int): String {
        val safe = count.coerceIn(0, count(text))
        if (safe == 0) return ""
        return text.substring(0, text.offsetByCodePoints(0, safe))
    }
}
