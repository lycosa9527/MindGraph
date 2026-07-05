import { describe, expect, it } from 'vitest'

import {
  CANVAS_WORKSHEET_TEXT_MENU_ITEM,
} from '@/config/canvasExportMenu'
import {
  CLASSROOM_WORKSHEET_TEXT_PRESET,
  DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
  hasActiveWorksheetHeader,
  loadCanvasWorksheetTextOptions,
  saveCanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'
import { buildWorksheetHeaderElement } from '@/utils/diagramWorksheetHeader'
import { fitImageRectInA4Region } from '@/utils/diagramPdfExport'

describe('canvasWorksheetText', () => {
  it('defines worksheet text menu metadata', () => {
    expect(CANVAS_WORKSHEET_TEXT_MENU_ITEM.labelKey).toBe('canvas.topBar.addWorksheetText')
    expect(CANVAS_WORKSHEET_TEXT_MENU_ITEM.divided).toBe(true)
  })

  it('defaults classroom fields to hidden until configured', () => {
    expect(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS.showTopic).toBe(false)
    expect(hasActiveWorksheetHeader(DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS)).toBe(false)
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

  it('persists worksheet text options in sessionStorage', () => {
    const custom = {
      ...DEFAULT_CANVAS_WORKSHEET_TEXT_OPTIONS,
      showDate: false,
      instructionText: 'Custom task',
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
})
