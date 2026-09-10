import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'

import { applyCanvasSessionReset } from '@/composables/canvasPage/applyCanvasSessionReset'
import {
  confirmCanvasLibraryDiagramOpen,
  decideCanvasLibraryDiagramOpen,
} from '@/composables/canvasPage/canvasLibraryDiagramOpen'
import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { isCanvasPristineForTypeSwitch } from '@/composables/canvasPage/isCanvasPristineForTypeSwitch'
import { switchCanvasDiagramType } from '@/composables/canvasPage/switchCanvasDiagramType'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { eventBus } from '@/composables/core/useEventBus'
import { adoptOpenCanvasSessionScope } from '@/composables/kitty/adoptOpenCanvasSessionScope'
import {
  consumeKittyPendingDesktopExplain,
  stashKittyPendingDesktopExplain,
} from '@/composables/kitty/kittyPendingCanvasAction'
import { applyKittySelectionTarget } from '@/composables/kitty/kittySelectionApply'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { splitSavedLlmResultsFromSpec } from '@/stores/llmResultsPersist'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { mindMapLibraryLoadOptions } from '@/utils/mindMapLibraryLoadOptions'

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

interface ReloadLibraryDiagramQueued {
  kind?: unknown
  diagram_library_id?: unknown
  title?: unknown
}

interface ExplainNodeQueued {
  kind?: unknown
  node_id?: unknown
  node_label?: unknown
  diagram_library_id?: unknown
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
 * Force-reload a library diagram into Pinia (even when already active).
 * Used after mobile vision rebuild writes a new library snapshot.
 */
export async function handleKittyReloadLibraryDiagramAction(
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
  const act = action as ReloadLibraryDiagramQueued
  if (act.kind !== 'reload_library_diagram') {
    return
  }
  const targetId = typeof act.diagram_library_id === 'string' ? act.diagram_library_id.trim() : ''
  if (targetId.length === 0) {
    return
  }

  const onCanvas = options.routePath === '/canvas' || options.routePath.startsWith('/canvas/')
  if (!onCanvas) {
    await options.router
      .push({ path: '/canvas', query: { diagramId: targetId } })
      .catch(() => undefined)
    return
  }

  const currentId = options.savedDiagramsStore.activeDiagramId?.trim() ?? ''
  if (currentId && currentId !== targetId) {
    await handleKittyOpenLibraryDiagramAction(
      { kind: 'open_library_diagram', diagram_library_id: targetId, title: act.title },
      options
    )
    return
  }

  // Authoritative reload so we pick up the mobile-written snapshot.
  const result = await options.savedDiagramsStore.getDiagram(targetId, { force: true })
  if (!result.ok || !result.diagram?.spec) {
    return
  }
  const diagramStore = useDiagramStore()
  const spec = result.diagram.spec as Record<string, unknown>
  const diagramType = (result.diagram.diagram_type || 'mindmap') as DiagramType
  const { specForLoad, saved: llmResults } = splitSavedLlmResultsFromSpec(spec)
  const llmResultsStore = useLLMResultsStore()
  if (llmResults) {
    llmResultsStore.restoreFromSaved(llmResults, diagramType)
  } else {
    llmResultsStore.reset()
  }
  const loaded = diagramStore.loadFromSpec(
    specForLoad,
    diagramType,
    mindMapLibraryLoadOptions(diagramType, specForLoad)
  )
  if (loaded) {
    options.savedDiagramsStore.setActiveDiagram(targetId)
    traceKittyWorkflow('desktop', 'desktop_nav', `reload_library ${targetId.slice(0, 12)}`, {
      scope: targetId,
    })
  }
}

function isDesktopCanvasPath(routePath: string): boolean {
  return routePath === '/canvas' || routePath.startsWith('/canvas/')
}

function emitDesktopNodeExplain(nodeId: string): void {
  applyKittySelectionTarget({ nodeId }, { canvasHighlight: true })
  eventBus.emit('mindmap:explain_node_requested', { nodeId })
  traceKittyWorkflow('desktop', 'desktop_nav', `explain_node ${nodeId.slice(0, 12)}`)
}

/** Mobile node-chip tap → desktop 节点解释 (same event as the canvas floating toolbar). */
export async function handleKittyExplainNodeAction(
  action: unknown,
  options?: {
    routePath: string
    savedDiagramsStore: SavedDiagramsStore
    router: Router
    t: (key: string, fallback?: string) => string
  }
): Promise<void> {
  if (action == null || typeof action !== 'object') {
    return
  }
  const act = action as ExplainNodeQueued
  if (act.kind !== 'explain_node') {
    return
  }
  const nodeId = typeof act.node_id === 'string' ? act.node_id.trim() : ''
  if (!nodeId) {
    return
  }
  const libId = typeof act.diagram_library_id === 'string' ? act.diagram_library_id.trim() : ''
  const onCanvas = options != null && isDesktopCanvasPath(options.routePath)
  const currentLib = options?.savedDiagramsStore.activeDiagramId?.trim() ?? ''
  const sameDiagram = !libId || !currentLib || currentLib === libId
  if (options == null || (onCanvas && sameDiagram)) {
    emitDesktopNodeExplain(nodeId)
    return
  }
  stashKittyPendingDesktopExplain(nodeId, libId || undefined)
  if (libId) {
    const opened = await handleKittyOpenLibraryDiagramAction(
      { kind: 'open_library_diagram', diagram_library_id: libId },
      options
    )
    if (!opened) {
      consumeKittyPendingDesktopExplain()
    }
    return
  }
  if (!onCanvas) {
    await options.router.push({ path: '/canvas' }).catch(() => undefined)
  }
}

export async function handleKittyOpenLibraryDiagramAction(
  action: unknown,
  options: {
    routePath: string
    savedDiagramsStore: SavedDiagramsStore
    router: Router
    t: (key: string, fallback?: string) => string
  }
): Promise<boolean> {
  if (action == null || typeof action !== 'object') {
    return false
  }
  const act = action as OpenLibraryDiagramQueued
  if (act.kind !== 'open_library_diagram') {
    return false
  }
  const targetId = typeof act.diagram_library_id === 'string' ? act.diagram_library_id.trim() : ''
  if (targetId.length === 0) {
    return false
  }
  const targetTitle =
    typeof act.title === 'string' && act.title.trim().length > 0 ? act.title.trim() : targetId

  const currentId = options.savedDiagramsStore.activeDiagramId?.trim() ?? ''
  const decision = decideCanvasLibraryDiagramOpen(options.routePath, currentId, targetId)
  if (decision === 'noop') {
    return true
  }

  if (decision === 'confirm') {
    const currentTitle =
      options.savedDiagramsStore.diagrams.find((row) => row.id === currentId)?.title ?? currentId
    const accepted = await confirmCanvasLibraryDiagramOpen({
      title: options.t('kitty.desktopJumpConfirmTitle', '切换导图'),
      message: options.t(
        'kitty.desktopJumpConfirmBody',
        `手机 Kitty 请求打开「${targetTitle}」。当前画布是「${currentTitle}」。是否跳转？`
      ),
      confirmButtonText: options.t('kitty.desktopJumpConfirmOk', '跳转'),
      cancelButtonText: options.t('common.cancel', '取消'),
    })
    if (!accepted) {
      return false
    }
  }

  await options.router
    .push({ path: '/canvas', query: { diagramId: targetId } })
    .catch(() => undefined)
  traceKittyWorkflow('desktop', 'desktop_nav', `open_library ${targetId.slice(0, 12)}`, {
    scope: targetId,
  })
  return true
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
        await swissGlassConfirm(
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
    return
  }
  if (kind === 'reload_library_diagram') {
    await handleKittyReloadLibraryDiagramAction(action, options)
    return
  }
  if (kind === 'explain_node') {
    await handleKittyExplainNodeAction(action, options)
  }
}
