import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.stubGlobal(
  'matchMedia',
  vi.fn(() => ({
    matches: false,
    media: '',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
)

vi.mock('element-plus', () => ({
  ElMessageBox: {
    confirm: vi.fn(),
  },
}))

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

vi.mock('@/composables/canvasPage/isCanvasPristineForTypeSwitch', () => ({
  isCanvasPristineForTypeSwitch: vi.fn(() => true),
}))

vi.mock('@/composables/canvasPage/switchCanvasDiagramType', () => ({
  switchCanvasDiagramType: vi.fn(() => true),
}))

vi.mock('@/composables/canvasPage/applyCanvasSessionReset', () => ({
  applyCanvasSessionReset: vi.fn(),
}))

import { switchCanvasDiagramType } from '@/composables/canvasPage/switchCanvasDiagramType'
import {
  adoptOpenCanvasSessionScope,
  handleKittyOpenCanvasAction,
} from '@/composables/kitty/kittyDesktopActionHandlers'
import { useOneSentenceStore } from '@/stores/oneSentence'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

describe('kittyDesktopActionHandlers open_canvas session_scope', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(switchCanvasDiagramType).mockClear()
    vi.mocked(switchCanvasDiagramType).mockReturnValue(true)
  })

  it('adopts mobile session_scope onto one-sentence ephemeral SoT', () => {
    const scope = '101327e1-2226-4483-b376-8824bccfeb73'
    const oneSentence = useOneSentenceStore()
    const saved = useSavedDiagramsStore()
    saved.setActiveDiagram('old-lib-id')

    adoptOpenCanvasSessionScope(scope)

    expect(oneSentence.diagramScope).toBe(scope)
    expect(oneSentence.ephemeralScope).toBe(scope)
    expect(saved.activeDiagramId).toBeNull()
  })

  it('switch_canvas path adopts session_scope after type switch', async () => {
    const scope = '101327e1-2226-4483-b376-8824bccfeb73'
    const router = { push: vi.fn(), replace: vi.fn() }

    await handleKittyOpenCanvasAction(
      {
        kind: 'open_canvas',
        diagram_type: 'mindmap',
        session_scope: scope,
      },
      router as never,
      { routePath: '/canvas' }
    )

    expect(switchCanvasDiagramType).toHaveBeenCalled()
    expect(useOneSentenceStore().diagramScope).toBe(scope)
    expect(router.push).not.toHaveBeenCalled()
  })

  it('navigating open_canvas puts kitty_scope in query', async () => {
    const scope = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    const router = {
      push: vi.fn().mockResolvedValue(undefined),
      replace: vi.fn(),
    }

    await handleKittyOpenCanvasAction(
      {
        kind: 'open_canvas',
        diagram_type: 'mindmap',
        session_scope: scope,
      },
      router as never,
      { routePath: '/dashboard' }
    )

    expect(router.push).toHaveBeenCalledWith({
      path: '/canvas',
      query: expect.objectContaining({
        type: 'mindmap',
        kitty_scope: scope,
      }),
    })
    expect(useOneSentenceStore().diagramScope).toBe(scope)
  })
})
