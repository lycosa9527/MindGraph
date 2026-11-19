package com.mindgraph.glasssheet

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class QrZoomTest {
    @Test
    fun cropKeepsTheCornerPatch() {
        val src = Luma(ByteArray(12 * 10) { it.toByte() }, 12, 10)
        val crop = cropLuma(src, 8, 6, 4, 4)
        assertNotNull(crop)
        assertEquals(4, crop!!.width)
        assertEquals(4, crop.height)
        assertEquals(src.bytes[6 * 12 + 8], crop.bytes[0])
    }

    @Test
    fun scaleTriplesASmallPatch() {
        val src = Luma(byteArrayOf(1, 2, 3, 4), 2, 2)
        val scaled = scaleLuma(src, 3)
        assertEquals(6, scaled.width)
        assertEquals(6, scaled.height)
        assertEquals(2.toByte(), scaled.bytes[0 * 6 + 3])
    }

    @Test
    fun finderBoxPadsAroundTheThreeSquares() {
        val box = finderCrop(200, 100, floatArrayOf(20f, 80f, 20f), floatArrayOf(10f, 10f, 70f))
        assertNotNull(box)
        assertEquals(0, box!![0])
        assertEquals(0, box[1])
        assert(box[2] > 80)
        assert(box[3] > 70)
    }

    @Test
    fun zoomGrowsATinyCropTowardTheDecoder() {
        assertEquals(4, QrDecoder.zoomFactor(80))
        assertEquals(1, QrDecoder.zoomFactor(480))
    }
}
