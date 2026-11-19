package com.mindgraph.glasssheet

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GlassNavTest {
    @Test
    fun rightFromTheCourseSelectsCanvasAndConfirmOpensThePad() {
        val nav = GlassNav()
        assertEquals(GlassMode.COURSE, nav.mode)
        assertNull(nav.onKey(NavKey.CONFIRM))
        assertTrue(nav.onBar)
        assertNull(nav.onKey(NavKey.RIGHT))
        assertEquals(GlassMode.CANVAS, nav.mode)
        assertTrue(nav.onBar)
        assertNull(nav.onKey(NavKey.CONFIRM))
        assertFalse(nav.onBar)
        assertEquals(RemoteAction.FIT, nav.pad.current())
    }

    @Test
    fun settingsSitBesideCanvasAndExitIsTheLastRow() {
        val nav = GlassNav()
        nav.onKey(NavKey.RIGHT)
        nav.onKey(NavKey.RIGHT)
        assertEquals(GlassMode.SETTINGS, nav.mode)
        assertTrue(nav.onBar)
        assertNull(nav.onKey(NavKey.CONFIRM))
        assertEquals(GlassSetting.BIND, nav.setting)
        assertNull(nav.onKey(NavKey.DOWN))
        assertEquals(GlassSetting.UNBIND, nav.setting)
        assertNull(nav.onKey(NavKey.DOWN))
        assertEquals(GlassSetting.EXIT, nav.setting)
        assertNull(nav.onKey(NavKey.UP))
        assertEquals(GlassSetting.UNBIND, nav.setting)
        assertNull(nav.onKey(NavKey.UP))
        assertEquals(GlassSetting.BIND, nav.setting)
        assertNull(nav.onKey(NavKey.UP))
        assertTrue(nav.onBar)
    }

    @Test
    fun downOnTheBarDoesNotOpenTheApp() {
        val nav = GlassNav()
        assertNull(nav.onKey(NavKey.DOWN))
        assertTrue(nav.onBar)
        assertEquals(GlassMode.COURSE, nav.mode)
    }

    @Test
    fun upFromTheTopOfThePadReturnsToTheBar() {
        val nav = GlassNav()
        nav.showCanvas()
        assertNull(nav.onKey(NavKey.UP))
        assertEquals(RemoteAction.PAN_UP, nav.pad.current())
        assertNull(nav.onKey(NavKey.UP))
        assertTrue(nav.onBar)
        assertEquals(GlassMode.CANVAS, nav.mode)
    }

    @Test
    fun leftOnTheBarReturnsToTheCourse() {
        val nav = GlassNav()
        nav.showCanvas()
        nav.onKey(NavKey.UP)
        nav.onKey(NavKey.UP)
        assertNull(nav.onKey(NavKey.LEFT))
        assertEquals(GlassMode.COURSE, nav.mode)
        assertTrue(nav.onBar)
        assertNull(nav.onKey(NavKey.LEFT))
        assertEquals(GlassMode.COURSE, nav.mode)
    }

    @Test
    fun confirmOnFitSendsFit() {
        val nav = GlassNav()
        nav.showCanvas()
        assertEquals(RemoteAction.FIT, nav.onKey(NavKey.CONFIRM))
    }

    @Test
    fun upFromTheLeftCellLandsOnPanUp() {
        val nav = GlassNav()
        nav.focus(RemoteAction.PAN_LEFT)
        assertNull(nav.onKey(NavKey.UP))
        assertEquals(RemoteAction.PAN_UP, nav.pad.current())
    }

    @Test
    fun lessonLineTypesByCharacter() {
        assertEquals(2, LessonLine.count("你好"))
        assertEquals("你", LessonLine.typed("你好", 1))
        assertEquals("你好", LessonLine.typed("你好", 8))
        assertEquals("", LessonLine.typed("你好", 0))
        assertEquals(3, LessonLine.count("a😊b"))
        assertEquals("a😊", LessonLine.typed("a😊b", 2))
    }

    @Test
    fun wordmarkGrowsFromTheM() {
        assertEquals("M", MindWordmark.textAt(1))
        assertEquals("Mind", MindWordmark.textAt(4))
        assertEquals("Mind Platform", MindWordmark.textAt(40))
    }

    @Test
    fun clockUsesTheDeviceHourCycle() {
        assertEquals("9:05", formatHudClock(9, 5, true))
        assertEquals("0:05", formatHudClock(0, 5, true))
        assertEquals("12:05", formatHudClock(0, 5, false))
        assertEquals("1:05", formatHudClock(13, 5, false))
    }

    @Test
    fun remoteUrlKeepsTheIngestHost() {
        val url = glassesRemoteUrl("http://127.0.0.1:9527/api/learning-space/glasses/ingest")
        assertEquals("http://127.0.0.1:9527/api/learning-space/glasses/remote", url)
    }

    @Test
    fun lessonTapIsNextAndHoldIsNotATap() {
        val tap = LessonTap()
        tap.press()
        assertEquals(true, tap.release())
        tap.press()
        assertEquals(true, tap.hold())
        assertEquals(false, tap.hold())
        assertEquals(false, tap.release())
        tap.press()
        tap.cancel()
        assertEquals(false, tap.release())
    }

    @Test
    fun playUrlPostsATapToTheIngestHost() {
        val play = glassesPlayUrl("http://192.168.0.147:9527/api/learning-space/glasses/ingest")
        assertEquals("http://192.168.0.147:9527/api/learning-space/glasses/play", play)
    }
}
