import { describe, expect, it } from 'vitest'

import {
  CANVAS_COMMUNITY_EXPORT_MENU_ITEM,
  CANVAS_RASTER_EXPORT_COMMANDS,
  CANVAS_STANDARD_EXPORT_MENU_ITEMS,
  type CanvasExportCommand,
} from '@/config/canvasExportMenu'
import {
  isPdfExportCommand,
  resolvePdfOrientationFromCommand,
  resolvePdfOrientationFromSize,
} from '@/utils/diagramPdfExport'

describe('canvasExportMenu', () => {
  it('lists png, svg, pdf variants, and mg in standard export menu order', () => {
    const commands = CANVAS_STANDARD_EXPORT_MENU_ITEMS.map((item) => item.command)
    expect(commands).toEqual(['png', 'svg', 'pdf_landscape', 'pdf_portrait', 'mg'])
  })

  it('marks mg as divided from raster formats', () => {
    const mgItem = CANVAS_STANDARD_EXPORT_MENU_ITEMS.find((item) => item.command === 'mg')
    expect(mgItem?.divided).toBe(true)
  })

  it('covers all raster export commands used by useDiagramExport', () => {
    const rasterInMenu = CANVAS_STANDARD_EXPORT_MENU_ITEMS
      .map((item) => item.command)
      .filter((command): command is 'png' | 'svg' | 'pdf_landscape' | 'pdf_portrait' =>
        CANVAS_RASTER_EXPORT_COMMANDS.includes(command as 'png' | 'svg' | 'pdf_landscape' | 'pdf_portrait')
      )
    expect(rasterInMenu).toEqual([...CANVAS_RASTER_EXPORT_COMMANDS])
  })

  it('uses canvas top bar label keys for each menu item', () => {
    for (const item of CANVAS_STANDARD_EXPORT_MENU_ITEMS) {
      expect(item.labelKey.startsWith('canvas.topBar.export')).toBe(true)
    }
  })

  it('defines community export menu metadata', () => {
    expect(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.command).toBe('community')
    expect(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.labelKey).toBe('canvas.topBar.shareCommunity')
    expect(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.divided).toBe(true)
  })

  it('includes community as an optional export command in the event bus contract', () => {
    const community: CanvasExportCommand = 'community'
    expect(community).toBe('community')
  })
})

describe('diagramPdfExport', () => {
  it('resolves landscape for wide diagrams and portrait for tall diagrams', () => {
    expect(resolvePdfOrientationFromSize(1200, 800)).toBe('landscape')
    expect(resolvePdfOrientationFromSize(800, 1200)).toBe('portrait')
  })

  it('honors explicit pdf menu commands', () => {
    expect(resolvePdfOrientationFromCommand('pdf_landscape', 800, 1200)).toBe('landscape')
    expect(resolvePdfOrientationFromCommand('pdf_portrait', 1200, 800)).toBe('portrait')
  })

  it('auto-matches legacy pdf command to diagram aspect ratio', () => {
    expect(resolvePdfOrientationFromCommand('pdf', 1200, 800)).toBe('landscape')
    expect(resolvePdfOrientationFromCommand('pdf', 800, 1200)).toBe('portrait')
  })

  it('recognizes pdf export command aliases', () => {
    expect(isPdfExportCommand('pdf_landscape')).toBe(true)
    expect(isPdfExportCommand('pdf_portrait')).toBe(true)
    expect(isPdfExportCommand('pdf')).toBe(true)
    expect(isPdfExportCommand('png')).toBe(false)
  })
})
