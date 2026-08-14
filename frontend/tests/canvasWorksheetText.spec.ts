import { describe, expect, it } from 'vitest'

import {
  CANVAS_WORKSHEET_TEXT_MENU_ITEM,
} from '@/config/canvasExportMenu'
import {
  CLASSROOM_WORKSHEET_TEXT_PRESET,
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  hasActiveWorksheetHeader,
  loadCanvasWorksheetTextOptions,
  resolveWorksheetTopicText,
  saveCanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'
import { buildWorksheetHeaderElement } from '@/utils/diagramWorksheetHeader'
import { fitImageRectInA4Region } from '@/utils/diagramPdfExport'
import { mergeCanvasExportOptions } from '@/utils/mergeCanvasExportOptions'

describe('canvasWorksheetText', () => {
  it('defines worksheet text menu metadata', () => {
    expect(CANVAS_WORKSHEET_TEXT_MENU_ITEM.labelKey).toBe('canvas.topBar.addWorksheetText')
    expect('divided' in CANVAS_WORKSHEET_TEXT_MENU_ITEM).toBe(false)
  })

  it('defaults classroom fields to shown', () => {
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showTopic).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showName).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showClass).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showDate).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showInstruction).toBe(true)
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.topicText).toBe('')
    expect(hasActiveWorksheetHeader(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS)).toBe(true)
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
    const element = buildWorksheetHeaderElement(
      'Photosynthesis',
      CLASSROOM_WORKSHEET_TEXT_PRESET,
      {
        name: 'Name:',
        className: 'Class:',
        date: 'Date:',
        instructionPrefix: 'Task:',
        defaultInstruction: 'Fill in the blanks.',
      }
    )
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
