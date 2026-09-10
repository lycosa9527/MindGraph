import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it, vi } from 'vitest'

import {
  CANVAS_EDITOR_PATH_MOBILE,
  CANVAS_ENTRY_PATH_KEY,
  canvasEditorPathForRoute,
  canvasPathForImportNavigation,
  defaultMindGraphLandingPath,
  isMindGraphLandingPath,
  navigateBackFromCanvas,
} from '@/utils/canvasBackNavigation'

describe('canvasBackNavigation', () => {
  it('identifies MindGraph landing paths', () => {
    expect(isMindGraphLandingPath('/mindgraph')).toBe(true)
    expect(isMindGraphLandingPath('/m/mindgraph')).toBe(true)
    expect(isMindGraphLandingPath('/m/canvas')).toBe(false)
  })

  it('keeps mobile editor paths on /m/canvas', () => {
    expect(canvasEditorPathForRoute(CANVAS_EDITOR_PATH_MOBILE)).toBe('/m/canvas')
    expect(canvasEditorPathForRoute('/canvas')).toBe('/canvas')
  })

  it('opens mobile canvas from mobile MindMate and MindGraph pages', () => {
    expect(canvasEditorPathForRoute('/m/mindmate')).toBe('/m/canvas')
    expect(canvasEditorPathForRoute('/m/mindgraph')).toBe('/m/canvas')
    expect(canvasEditorPathForRoute('/mindmate')).toBe('/canvas')
  })

  it('routes import navigation to mobile canvas from mobile routes', () => {
    expect(canvasPathForImportNavigation('/m/mindgraph')).toBe('/m/canvas')
    expect(canvasPathForImportNavigation('/mindgraph')).toBe('/canvas')
    expect(canvasPathForImportNavigation('/m/mindmate')).toBe('/m/canvas')
  })

  it('defaults mobile canvas back to /m/mindgraph', () => {
    expect(defaultMindGraphLandingPath('/m/canvas')).toBe('/m/mindgraph')
    expect(defaultMindGraphLandingPath('/canvas')).toBe('/mindgraph')
  })

  it('navigateBackFromCanvas replaces to stored MindGraph entry in one step', () => {
    sessionStorage.setItem(CANVAS_ENTRY_PATH_KEY, '/mindgraph')
    const replace = vi.fn()
    navigateBackFromCanvas({ replace } as never, '/canvas')
    expect(replace).toHaveBeenCalledWith({ path: '/mindgraph' })
    sessionStorage.removeItem(CANVAS_ENTRY_PATH_KEY)
  })

  it('navigateBackFromCanvas replaces to stored MindMate entry in one step', () => {
    sessionStorage.setItem(CANVAS_ENTRY_PATH_KEY, '/mindmate')
    const replace = vi.fn()
    navigateBackFromCanvas({ replace } as never, '/canvas')
    expect(replace).toHaveBeenCalledWith({ path: '/mindmate' })
    sessionStorage.removeItem(CANVAS_ENTRY_PATH_KEY)
  })

  it('drops the translate preview before replacing to the gallery', () => {
    const src = readFileSync(
      resolve(dirname(fileURLToPath(import.meta.url)), '../src/utils/canvasBackNavigation.ts'),
      'utf8'
    )
    expect(src).toContain('discardCanvasTranslatePreview')
  })

  it('navigateBackFromCanvas falls back to landing when entry is missing', () => {
    sessionStorage.removeItem(CANVAS_ENTRY_PATH_KEY)
    const replace = vi.fn()
    navigateBackFromCanvas({ replace } as never, '/canvas')
    expect(replace).toHaveBeenCalledWith({ path: '/mindgraph' })
  })
})
