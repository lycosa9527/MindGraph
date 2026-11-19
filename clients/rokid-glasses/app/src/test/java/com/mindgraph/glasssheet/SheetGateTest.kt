package com.mindgraph.glasssheet

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SheetGateTest {
    private val sheetA = "11111111-1111-1111-1111-111111111111"
    private val sheetB = "22222222-2222-2222-2222-222222222222"

    @Test
    fun firesAfterThreeStableFrames() {
        val gate = SheetGate()
        assertFalse(gate.onFrame(sheetA, 0L))
        assertFalse(gate.onFrame(sheetA, 30L))
        assertTrue(gate.onFrame(sheetA, 60L))
    }

    @Test
    fun ignoresTheSameSheetUntilItLeaves() {
        val gate = SheetGate(awayMillis = 800L)
        repeat(3) { index -> gate.onFrame(sheetA, index * 30L) }
        assertFalse(gate.onFrame(sheetA, 200L))
        assertFalse(gate.onFrame(null, 500L))
        assertFalse(gate.onFrame(sheetA, 600L))
        assertFalse(gate.onFrame(null, 1500L))
        assertFalse(gate.onFrame(sheetA, 1600L))
        assertFalse(gate.onFrame(sheetA, 1630L))
        assertTrue(gate.onFrame(sheetA, 1660L))
    }

    @Test
    fun aFailedSendCanFireAgainImmediately() {
        val gate = SheetGate()
        repeat(3) { index -> gate.onFrame(sheetA, index * 30L) }
        gate.forget()
        assertFalse(gate.onFrame(sheetA, 200L))
        assertFalse(gate.onFrame(sheetA, 230L))
        assertTrue(gate.onFrame(sheetA, 260L))
    }

    @Test
    fun nextSheetFiresWithoutWaiting() {
        val gate = SheetGate()
        repeat(3) { index -> gate.onFrame(sheetA, index * 30L) }
        assertFalse(gate.onFrame(sheetB, 200L))
        assertFalse(gate.onFrame(sheetB, 230L))
        assertTrue(gate.onFrame(sheetB, 260L))
    }
}
