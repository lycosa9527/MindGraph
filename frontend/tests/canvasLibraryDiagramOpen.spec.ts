import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  confirmCanvasLibraryDiagramOpen,
  decideCanvasLibraryDiagramOpen,
  isCanvasEditorRoutePath,
} from '@/composables/canvasPage/canvasLibraryDiagramOpen'

const { confirmMock, loadElMessageBox } = vi.hoisted(() => {
  const confirm = vi.fn()
  return {
    confirmMock: confirm,
    loadElMessageBox: vi.fn(async () => ({ confirm })),
  }
})

vi.mock('@/composables/core/notifications', () => ({
  loadElMessageBox,
}))

describe('canvasLibraryDiagramOpen', () => {
  beforeEach(() => {
    confirmMock.mockReset()
    loadElMessageBox.mockClear()
  })

  it('detects desktop and mobile canvas editor paths', () => {
    expect(isCanvasEditorRoutePath('/canvas')).toBe(true)
    expect(isCanvasEditorRoutePath('/m/canvas')).toBe(true)
    expect(isCanvasEditorRoutePath('/mindmate')).toBe(false)
    expect(isCanvasEditorRoutePath('/m/mindmate')).toBe(false)
  })

  it('no-ops when the target library diagram is already open on canvas', () => {
    expect(decideCanvasLibraryDiagramOpen('/canvas', 'diag-a', 'diag-a')).toBe('noop')
    expect(decideCanvasLibraryDiagramOpen('/m/canvas', 'diag-a', 'diag-a')).toBe('noop')
  })

  it('asks to confirm when switching to a different library diagram on canvas', () => {
    expect(decideCanvasLibraryDiagramOpen('/canvas', 'diag-a', 'diag-b')).toBe('confirm')
    expect(decideCanvasLibraryDiagramOpen('/m/canvas', 'diag-a', 'diag-b')).toBe('confirm')
  })

  it('navigates without confirm when leaving MindMate for canvas', () => {
    expect(decideCanvasLibraryDiagramOpen('/mindmate', 'diag-a', 'diag-b')).toBe('navigate')
    expect(decideCanvasLibraryDiagramOpen('/m/mindmate', null, 'diag-b')).toBe('navigate')
    expect(decideCanvasLibraryDiagramOpen('/canvas', null, 'diag-b')).toBe('navigate')
  })

  it('confirmCanvasLibraryDiagramOpen resolves true on accept and false on cancel', async () => {
    confirmMock.mockResolvedValueOnce(undefined)
    await expect(
      confirmCanvasLibraryDiagramOpen({
        title: 'Switch',
        message: 'Open B?',
        confirmButtonText: 'Open',
        cancelButtonText: 'Cancel',
      })
    ).resolves.toBe(true)

    confirmMock.mockRejectedValueOnce('cancel')
    await expect(
      confirmCanvasLibraryDiagramOpen({
        title: 'Switch',
        message: 'Open B?',
        confirmButtonText: 'Open',
        cancelButtonText: 'Cancel',
      })
    ).resolves.toBe(false)
  })
})
