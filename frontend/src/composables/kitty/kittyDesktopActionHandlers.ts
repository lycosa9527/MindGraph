import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { applyCanvasSessionReset } from '@/composables/canvasPage/applyCanvasSessionReset'
import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { isCanvasPristineForTypeSwitch } from '@/composables/canvasPage/isCanvasPristineForTypeSwitch'
import { switchCanvasDiagramType } from '@/composables/canvasPage/switchCanvasDiagramType'
import { loadElMessageBox } from '@/composables/core/notifications'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useDiagramStore, useLLMResultsStore, useOneSentenceStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

type SavedDiagramsStore = ReturnType<typeof useSavedDiagramsStore>

const VALID = new Set<string>(VALID_DIAGRAM_TYPES)
const SESSION_SCOPE_SAFE = /^[0-9a-zA-Z_-]+$/

interface OpenCanvasQueued {
  kind?: unknown
  diagram_type?: unknown
  topic?: unknown
  left?: unknown
  right?: unknown
  session_scope?: unknown
}

interface OpenLibraryDiagramQueued {
  kind?: unknown
  diagram_library_id?: unknown
  title?: unknown
}

function isDiagramType(slug: unknown): slug is DiagramType {
  return typeof slug === 'string' && VALID.has(slug)
}

function normalizeSessionScope(raw: unknown): string | null {
  if (typeof raw !== 'string') {
    return null
  }
  const cut = raw.trim()
  if (!cut || cut.length > 128 || !SESSION_SCOPE_SAFE.test(cut)) {
    return null
  }
  return cut
}

/**
 * Bind desktop Kitty / one-sentence scope to the mobile-issued session id.
 * Must run after canvas reset so a fresh blank canvas shares mobile's SoT.
 */
export function adoptOpenCanvasSessionScope(sessionScope: string): void {
  useOneSentenceStore().adoptEphemeralScope(sessionScope)
  useSavedDiagramsStore().clearActiveDiagram()
  traceKittyWorkflow('desktop', 'desktop_nav', `adopt_scope ${sessionScope.slice(0, 12)}`, {
    scope: sessionScope,
  })
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
      const ElMessageBox = await loadElMessageBox()
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

export async function handleKittyOpenCanvasAction(
  action: unknown,
  router: Router,
  options?: {
    routePath?: string
    route?: RouteLocationNormalizedLoaded
    t?: (key: string, fallback?: string) => string
  }
): Promise<void> {
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

  const topic = typeof act.topic === 'string' ? act.topic.trim() : ''
  const left = typeof act.left === 'string' ? act.left.trim() : ''
  const right = typeof act.right === 'string' ? act.right.trim() : ''
  const sessionScope = normalizeSessionScope(act.session_scope)
  const topicSeed = {
    topic: topic.length > 0 ? topic.slice(0, 512) : undefined,
    left: left.length > 0 ? left.slice(0, 256) : undefined,
    right: right.length > 0 ? right.slice(0, 256) : undefined,
  }

  const routePath = options?.routePath ?? ''
  const onCanvas = routePath === '/canvas' || routePath.startsWith('/canvas/')
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const pristine = isCanvasPristineForTypeSwitch(diagramStore, savedDiagramsStore, llmResultsStore)

  if (onCanvas && sessionScope != null && !pristine) {
    const t = options?.t
    if (t != null) {
      try {
        const ElMessageBox = await loadElMessageBox()
        await ElMessageBox.confirm(
          t(
            'kitty.desktopJumpConfirmBody',
            '手机 Kitty 请求打开新画布。当前画布有未保存内容，是否切换？'
          ),
          t('kitty.desktopJumpConfirmTitle', '切换导图'),
          {
            confirmButtonText: t('kitty.desktopJumpConfirmOk', '跳转'),
            cancelButtonText: t('common.cancel', '取消'),
            type: 'warning',
            distinguishCancelAndClose: true,
          }
        )
      } catch {
        return
      }
    }
  }

  if (onCanvas) {
    if (pristine || sessionScope != null) {
      const switched = switchCanvasDiagramType(dt, {
        topicSeed,
        router,
        route: options?.route,
      })
      if (switched) {
        if (sessionScope != null) {
          adoptOpenCanvasSessionScope(sessionScope)
        }
        traceKittyWorkflow('desktop', 'desktop_nav', `switch_canvas type=${dt}`)
        return
      }
    }
  }

  const q: Record<string, string> = { type: dt }
  if (topic.length > 0) {
    q.kitty_topic = topic.slice(0, 512)
  }
  if (left.length > 0) {
    q.kitty_left = left.slice(0, 256)
  }
  if (right.length > 0) {
    q.kitty_right = right.slice(0, 256)
  }
  if (sessionScope != null) {
    q.kitty_scope = sessionScope
  }
  // Navigating to a new canvas: reset local SoT before route so remount adopts scope.
  if (sessionScope != null && !onCanvas) {
    applyCanvasSessionReset()
    adoptOpenCanvasSessionScope(sessionScope)
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
    route?: RouteLocationNormalizedLoaded
    t: (key: string, fallback?: string) => string
  }
): Promise<void> {
  if (action == null || typeof action !== 'object') {
    return
  }
  const kind = (action as { kind?: unknown }).kind
  if (kind === 'open_canvas') {
    await handleKittyOpenCanvasAction(action, options.router, {
      routePath: options.routePath,
      route: options.route,
      t: options.t,
    })
    return
  }
  if (kind === 'open_library_diagram') {
    await handleKittyOpenLibraryDiagramAction(action, options)
  }
}
