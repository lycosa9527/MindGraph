import { describe, expect, it } from 'vitest'

import {
  CANVAS_COMMUNITY_EXPORT_MENU_ITEM,
  CANVAS_RASTER_EXPORT_COMMANDS,
  CANVAS_STANDARD_EXPORT_MENU_ITEMS,
  type CanvasExportCommand,
} from '@/config/canvasExportMenu'

describe('canvasExportMenu', () => {
  it('lists png, svg, pdf, and mg in standard export menu order', () => {
    const commands = CANVAS_STANDARD_EXPORT_MENU_ITEMS.map((item) => item.command)
    expect(commands).toEqual(['png', 'svg', 'pdf', 'mg'])
  })

  it('marks mg as divided from raster formats', () => {
    const mgItem = CANVAS_STANDARD_EXPORT_MENU_ITEMS.find((item) => item.command === 'mg')
    expect(mgItem?.divided).toBe(true)
  })

  it('covers all raster export commands used by useDiagramExport', () => {
    const rasterInMenu = CANVAS_STANDARD_EXPORT_MENU_ITEMS
      .map((item) => item.command)
      .filter((command): command is 'png' | 'svg' | 'pdf' =>
        CANVAS_RASTER_EXPORT_COMMANDS.includes(command as 'png' | 'svg' | 'pdf')
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
