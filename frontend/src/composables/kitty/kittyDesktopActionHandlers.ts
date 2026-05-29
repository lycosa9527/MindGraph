import type { Router } from 'vue-router'

import { ElMessageBox } from 'element-plus'

import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import type { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

type SavedDiagramsStore = ReturnType<typeof useSavedDiagramsStore>

const VALID = new Set<string>(VALID_DIAGRAM_TYPES)

interface OpenCanvasQueued {
  kind?: unknown
  diagram_type?: unknown
  topic?: unknown
  left?: unknown
  right?: unknown
}

interface OpenLibraryDiagramQueued {
  kind?: unknown
  diagram_library_id?: unknown
  title?: unknown
}

function isDiagramType(slug: unknown): slug is DiagramType {
  return typeof slug === 'string' && VALID.has(slug)
}

export async function handleKittyOpenLibraryDiagramAction(
  action: unknown,
  options: {
    routePath: string
    savedDiagramsStore: SavedDiagramsStore
    router: Router
    t: (key: string, fallback?: string) => string
  }
): Promise<void> {
  if (action == null || typeof action !== 'object') {
    return
  }
  const act = action as OpenLibraryDiagramQueued
  if (act.kind !== 'open_library_diagram') {
    return
  }
  const targetId = typeof act.diagram_library_id === 'string' ? act.diagram_library_id.trim() : ''
  if (targetId.length === 0) {
    return
  }
  const targetTitle =
    typeof act.title === 'string' && act.title.trim().length > 0 ? act.title.trim() : targetId

  const currentId = options.savedDiagramsStore.activeDiagramId?.trim() ?? ''
  const onCanvas = options.routePath === '/canvas' || options.routePath.startsWith('/canvas/')

  if (currentId === targetId && onCanvas) {
    return
  }

  if (currentId.length > 0 && currentId !== targetId) {
    const currentTitle =
      options.savedDiagramsStore.diagrams.find((row) => row.id === currentId)?.title ?? currentId
    try {
      await ElMessageBox.confirm(
        options.t(
          'kitty.desktopJumpConfirmBody',
          `手机 Kitty 请求打开「${targetTitle}」。当前画布是「${currentTitle}」。是否跳转？`
        ),
        options.t('kitty.desktopJumpConfirmTitle', '切换导图'),
        {
          confirmButtonText: options.t('kitty.desktopJumpConfirmOk', '跳转'),
          cancelButtonText: options.t('common.cancel', '取消'),
          type: 'warning',
          distinguishCancelAndClose: true,
        }
      )
    } catch {
      return
    }
  }

  await options.router
    .push({ path: '/canvas', query: { diagramId: targetId } })
    .catch(() => undefined)
  traceKittyWorkflow('desktop', 'desktop_nav', `open_library ${targetId.slice(0, 12)}`, {
    scope: targetId,
  })
}

export async function handleKittyOpenCanvasAction(action: unknown, router: Router): Promise<void> {
  if (action == null || typeof action !== 'object') {
    return
  }
  const act = action as OpenCanvasQueued
  if (act.kind !== 'open_canvas') {
    return
  }
  const dt = act.diagram_type
  if (!isDiagramType(dt)) {
    return
  }

  const q: Record<string, string> = { type: dt }
  const topic = typeof act.topic === 'string' ? act.topic.trim() : ''
  if (topic.length > 0) {
    q.kitty_topic = topic.slice(0, 512)
  }
  const left = typeof act.left === 'string' ? act.left.trim() : ''
  const right = typeof act.right === 'string' ? act.right.trim() : ''
  if (left.length > 0) {
    q.kitty_left = left.slice(0, 256)
  }
  if (right.length > 0) {
    q.kitty_right = right.slice(0, 256)
  }
  await router.push({ path: '/canvas', query: q }).catch(() => undefined)
  traceKittyWorkflow('desktop', 'desktop_nav', `open_canvas type=${dt}`)
}

export async function handleKittyDesktopQueuedAction(
  action: unknown,
  options: {
    routePath: string
    savedDiagramsStore: SavedDiagramsStore
    router: Router
    t: (key: string, fallback?: string) => string
  }
): Promise<void> {
  if (action == null || typeof action !== 'object') {
    return
  }
  const kind = (action as { kind?: unknown }).kind
  if (kind === 'open_canvas') {
    await handleKittyOpenCanvasAction(action, options.router)
    return
  }
  if (kind === 'open_library_diagram') {
    await handleKittyOpenLibraryDiagramAction(action, options)
  }
}
