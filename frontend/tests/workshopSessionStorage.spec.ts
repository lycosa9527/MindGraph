import { afterEach, describe, expect, it } from 'vitest'

import {
  clearWorkshopSessionStorage,
  persistWorkshopSession,
  queryWithSessionDiagramId,
  shouldClearWorkshopSessionOnNavigate,
  shouldRestoreWorkshopSession,
} from '@/utils/workshopSessionStorage'

afterEach(() => {
  clearWorkshopSessionStorage()
})

describe('shouldRestoreWorkshopSession', () => {
  it('does not restore when nothing is stored', () => {
    expect(shouldRestoreWorkshopSession({})).toBe(false)
  })

  it('restores a refresh of the same diagram id', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(shouldRestoreWorkshopSession({ diagramId: 'diag-1' })).toBe(true)
  })

  it('does not restore a different library diagram', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(shouldRestoreWorkshopSession({ diagramId: 'diag-2' })).toBe(false)
  })

  it('does not restore a new mind map from the gallery', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(shouldRestoreWorkshopSession({ type: 'mindmap' })).toBe(false)
  })

  it('does not restore an import landing', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(shouldRestoreWorkshopSession({ import: '1' })).toBe(false)
  })

  it('does not restore a bare /canvas refresh without a diagram id', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(shouldRestoreWorkshopSession({})).toBe(false)
  })
})

describe('queryWithSessionDiagramId', () => {
  it('pins the live room onto the URL once', () => {
    expect(queryWithSessionDiagramId({}, 'diag-1')).toEqual({ diagramId: 'diag-1' })
    expect(queryWithSessionDiagramId({ diagramId: 'diag-1' }, 'diag-1')).toBeNull()
  })
})

describe('shouldClearWorkshopSessionOnNavigate', () => {
  it('clears when leaving canvas for the gallery', () => {
    expect(shouldClearWorkshopSessionOnNavigate('/canvas', '/mindgraph', {})).toBe(true)
    expect(shouldClearWorkshopSessionOnNavigate('/m/canvas', '/m/mindgraph', {})).toBe(true)
  })

  it('clears canvas → new type without a diagram id', () => {
    expect(
      shouldClearWorkshopSessionOnNavigate('/canvas', '/canvas', { type: 'mindmap' })
    ).toBe(true)
  })

  it('clears canvas → a different saved diagram', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(
      shouldClearWorkshopSessionOnNavigate('/canvas', '/canvas', { diagramId: 'diag-2' })
    ).toBe(true)
  })

  it('keeps the room on refresh of the same diagram', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(
      shouldClearWorkshopSessionOnNavigate('/canvas', '/canvas', { diagramId: 'diag-1' })
    ).toBe(false)
  })

  it('clears when the gallery opens a new mind map', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(
      shouldClearWorkshopSessionOnNavigate('/mindgraph', '/canvas', { type: 'mindmap' }, true)
    ).toBe(true)
    expect(shouldClearWorkshopSessionOnNavigate('/mindgraph', '/canvas', {}, true)).toBe(true)
  })

  it('does not clear on a full-page refresh of /canvas', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    expect(shouldClearWorkshopSessionOnNavigate('/', '/canvas', {}, false)).toBe(false)
    expect(
      shouldClearWorkshopSessionOnNavigate('/', '/canvas', { diagramId: 'diag-1' }, false)
    ).toBe(false)
  })
})
