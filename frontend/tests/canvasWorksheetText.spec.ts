import { describe, expect, it } from 'vitest'

import { CANVAS_WORKSHEET_TEXT_MENU_ITEM } from '@/config/canvasExportMenu'
import {
  CLASSROOM_WORKSHEET_TEXT_PRESET,
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  hasActiveWorksheetHeader,
  isWorksheetCompareMode,
  loadCanvasWorksheetTextOptions,
  normalizeWorksheetCompareSlot,
  normalizeWorksheetMode,
  parseWorksheetCompareSlotKey,
  resolveWorksheetTopicText,
  saveCanvasWorksheetTextOptions,
  worksheetCompareSlotKey,
} from '@/config/canvasWorksheetText'
import { fitImageRectInA4Region } from '@/utils/diagramPdfExport'
import { buildWorksheetHeaderElement } from '@/utils/diagramWorksheetHeader'
import { mergeCanvasExportOptions } from '@/utils/mergeCanvasExportOptions'
import {
  fitImageInPanel,
  placeImageInComparePanel,
  splitWorksheetCompareRegion,
} from '@/utils/worksheetCompareLayout'

describe('canvasWorksheetText', () => {
  it('defines worksheet text menu metadata', () => {
    expect(CANVAS_WORKSHEET_TEXT_MENU_ITEM.labelKey).toBe('canvas.topBar.addWorksheetText')
    expect('divided' in CANVAS_WORKSHEET_TEXT_MENU_ITEM).toBe(false)
  })

  it('defaults classroom fields ready, with learning-sheet mode off', () => {
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.learningSheetMode).toBe(false)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showTopic).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showName).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showClass).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showDate).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showInstruction).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.topicText).toBe('')
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.worksheetMode).toBe('single')
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.compareLayout).toBe('horizontal')
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.compareLeft).toEqual({ kind: 'current' })
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.compareRight).toEqual({ kind: 'current' })
    expect(hasActiveWorksheetHeader(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS)).toBe(false)
    expect(
      hasActiveWorksheetHeader({
        ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
        learningSheetMode: true,
      })
    ).toBe(true)
  })

  it('normalizes compare mode and slot keys', () => {
    expect(normalizeWorksheetMode('compare')).toBe('compare')
    expect(normalizeWorksheetMode('other')).toBe('single')
    expect(normalizeWorksheetCompareSlot({ kind: 'model', id: 'express' })).toEqual({
      kind: 'model',
      id: 'express',
    })
    expect(normalizeWorksheetCompareSlot({ kind: 'model' })).toEqual({ kind: 'current' })
    expect(worksheetCompareSlotKey({ kind: 'snapshot', id: '3' })).toBe('snapshot:3')
    expect(parseWorksheetCompareSlotKey('model:qwen3-max')).toEqual({
      kind: 'model',
      id: 'qwen3-max',
    })
    expect(
      isWorksheetCompareMode({ ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS, worksheetMode: 'compare' })
    ).toBe(true)
  })

  it('detects inactive header when every field is hidden', () => {
    expect(
      hasActiveWorksheetHeader({
        ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
        showTopic: false,
        showName: false,
        showClass: false,
        showDate: false,
        showInstruction: false,
      })
    ).toBe(false)
  })

  it('resolves topic override before diagram title fallback', () => {
    expect(
      resolveWorksheetTopicText(
        { ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS, topicText: '  Print Title  ' },
        'Diagram Title'
      )
    ).toBe('Print Title')
    expect(
      resolveWorksheetTopicText(
        { ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS, topicText: '' },
        'Diagram Title'
      )
    ).toBe('Diagram Title')
  })

  it('persists worksheet text options in sessionStorage', () => {
    const custom = {
      ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
      showDate: false,
      instructionText: 'Custom task',
      topicText: 'Custom topic',
    }
    saveCanvasWorksheetTextOptions(custom)
    expect(loadCanvasWorksheetTextOptions()).toEqual(custom)
  })
})

describe('diagramWorksheetHeader', () => {
  it('builds header DOM with topic, meta row, and instruction', () => {
    const element = buildWorksheetHeaderElement('Photosynthesis', CLASSROOM_WORKSHEET_TEXT_PRESET, {
      name: 'Name:',
      className: 'Class:',
      date: 'Date:',
      instructionPrefix: 'Task:',
      defaultInstruction: 'Fill in the blanks.',
    })
    expect(element).not.toBeNull()
    expect(element?.textContent).toContain('Photosynthesis')
    expect(element?.textContent).toContain('Name:')
    expect(element?.textContent).toContain('Class:')
    expect(element?.textContent).toContain('Date:')
    expect(element?.textContent).toContain('Task:Fill in the blanks.')
  })

  it('returns null when no header fields are enabled', () => {
    const element = buildWorksheetHeaderElement(
      'Topic',
      {
        ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
        showTopic: false,
        showName: false,
        showClass: false,
        showDate: false,
        showInstruction: false,
      },
      {
        name: 'Name:',
        className: 'Class:',
        date: 'Date:',
        instructionPrefix: 'Task:',
        defaultInstruction: 'Fill in the blanks.',
      }
    )
    expect(element).toBeNull()
  })
})

describe('mergeCanvasExportOptions', () => {
  it('keeps plain PDF header-free when caller omits worksheetText', () => {
    const merged = mergeCanvasExportOptions({
      colorMode: 'wireframe',
      layout: 'portrait',
      answerMode: 'include',
    })
    expect(merged.colorMode).toBe('wireframe')
    expect(merged.layout).toBe('portrait')
    expect(merged.worksheetText).toBeUndefined()
  })

  it('attaches worksheetText only when fallback is provided', () => {
    const merged = mergeCanvasExportOptions(
      { colorMode: 'wireframe', layout: 'portrait', answerMode: 'include' },
      CLASSROOM_WORKSHEET_TEXT_PRESET
    )
    expect(merged.worksheetText).toEqual(CLASSROOM_WORKSHEET_TEXT_PRESET)
  })

  it('prefers explicit worksheetText from the caller', () => {
    const explicit = {
      ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
      showName: false,
      topicText: 'Override',
    }
    const merged = mergeCanvasExportOptions(
      {
        colorMode: 'color',
        layout: 'landscape',
        answerMode: 'exclude',
        worksheetText: explicit,
      },
      CLASSROOM_WORKSHEET_TEXT_PRESET
    )
    expect(merged.worksheetText).toEqual(explicit)
  })

  it('preserves runtime comparePair through merge', () => {
    const blob = new Blob(['x'], { type: 'image/png' })
    const comparePair = {
      left: {
        dataUrl: 'data:image/png;base64,AA==',
        width: 10,
        height: 10,
        label: 'A',
        blob,
      },
      right: {
        dataUrl: 'data:image/png;base64,BB==',
        width: 12,
        height: 12,
        label: 'B',
        blob,
      },
    }
    const merged = mergeCanvasExportOptions({
      colorMode: 'color',
      layout: 'landscape',
      answerMode: 'exclude',
      worksheetText: {
        ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
        worksheetMode: 'compare',
      },
      comparePair,
    })
    expect(merged.comparePair).toBe(comparePair)
    expect(merged.worksheetText?.worksheetMode).toBe('compare')
  })
})

describe('worksheetCompareLayout', () => {
  it('splits a region into equal left/right panels with a gap', () => {
    const layout = splitWorksheetCompareRegion(10, 40, 200, 100, 8, 6)
    expect(layout.left.width).toBeCloseTo(96)
    expect(layout.right.width).toBeCloseTo(96)
    expect(layout.right.x).toBeCloseTo(10 + 96 + 8)
    expect(layout.left.height).toBeCloseTo(94)
    expect(layout.arrangement).toBe('horizontal')
  })

  it('splits a region into equal top/bottom panels when vertical', () => {
    const layout = splitWorksheetCompareRegion(10, 40, 200, 100, 8, 6, 'vertical')
    expect(layout.arrangement).toBe('vertical')
    expect(layout.first.width).toBeCloseTo(200)
    expect(layout.second.width).toBeCloseTo(200)
    expect(layout.first.height).toBeCloseTo((100 - 8 - 12) / 2)
    expect(layout.second.y).toBeCloseTo(40 + layout.first.height + 6 + 8)
  })

  it('fits an image inside a panel while preserving aspect ratio', () => {
    const fitted = fitImageInPanel(1600, 900, { x: 0, y: 0, width: 100, height: 80 })
    expect(fitted.width).toBeLessThanOrEqual(100)
    expect(fitted.height).toBeLessThanOrEqual(80)
    expect(fitted.width / fitted.height).toBeCloseTo(1600 / 900, 5)
  })

  it('places a scaled image with offsets inside a compare panel', () => {
    const panel = { x: 0, y: 0, width: 100, height: 80 }
    const centered = placeImageInComparePanel(1600, 900, panel, 0, 0, 0.5)
    const shifted = placeImageInComparePanel(1600, 900, panel, 1, -1, 0.5)
    expect(centered.width).toBeLessThan(fitImageInPanel(1600, 900, panel).width)
    expect(shifted.x).toBeGreaterThan(centered.x)
    expect(shifted.y).toBeLessThan(centered.y)
  })
})

describe('diagramPdfExport worksheet layout', () => {
  it('fits diagram below a reserved header region', () => {
    const pdf = {
      internal: {
        pageSize: {
          getWidth: () => 297,
          getHeight: () => 210,
        },
      },
    }
    const rect = fitImageRectInA4Region(pdf, 1600, 900, 40, 10)
    expect(rect.y).toBeGreaterThan(40)
    expect(rect.width).toBeLessThanOrEqual(277)
    expect(rect.height).toBeLessThanOrEqual(160)
  })

  it('shifts fitted diagram by normalized offsets', () => {
    const pdf = {
      internal: {
        pageSize: {
          getWidth: () => 297,
          getHeight: () => 210,
        },
      },
    }
    // Scale < 1 leaves free space on both axes (max-fit always fills one axis).
    const centered = fitImageRectInA4Region(pdf, 800, 800, 40, 10, 0, 0, 0.5)
    const shifted = fitImageRectInA4Region(pdf, 800, 800, 40, 10, 1, -1, 0.5)
    expect(shifted.x).toBeGreaterThan(centered.x)
    expect(shifted.y).toBeLessThan(centered.y)
  })

  it('shrinks the fitted diagram by a bottom crop and recenters it', () => {
    const pdf = {
      internal: {
        pageSize: {
          getWidth: () => 297,
          getHeight: () => 210,
        },
      },
    }
    const full = fitImageRectInA4Region(pdf, 1600, 900, 40, 10, 0, 0, 1)
    const cropped = fitImageRectInA4Region(pdf, 1600, 900, 40, 10, 0, 0, 1, {
      top: 0,
      right: 0,
      bottom: 0.2,
      left: 0,
    })
    expect(cropped.width).toBeCloseTo(full.width)
    expect(cropped.height).toBeCloseTo(full.height * 0.8)
    expect(cropped.y).toBeGreaterThan(full.y)
  })

  it('scales fitted diagram relative to max-fit size', () => {
    const pdf = {
      internal: {
        pageSize: {
          getWidth: () => 297,
          getHeight: () => 210,
        },
      },
    }
    const full = fitImageRectInA4Region(pdf, 1600, 900, 40, 10, 0, 0, 1)
    const half = fitImageRectInA4Region(pdf, 1600, 900, 40, 10, 0, 0, 0.5)
    expect(half.width).toBeCloseTo(full.width * 0.5, 5)
    expect(half.height).toBeCloseTo(full.height * 0.5, 5)
  })
})
