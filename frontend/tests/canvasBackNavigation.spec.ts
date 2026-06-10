import { describe, expect, it } from 'vitest'

import {
  CANVAS_EDITOR_PATH_MOBILE,
  canvasEditorPathForRoute,
  canvasPathForImportNavigation,
  isMindGraphLandingPath,
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

  it('routes import navigation to mobile canvas from mobile routes', () => {
    expect(canvasPathForImportNavigation('/m/mindgraph')).toBe('/m/canvas')
    expect(canvasPathForImportNavigation('/mindgraph')).toBe('/canvas')
  })
})
