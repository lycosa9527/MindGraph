import { DEFAULT_CENTER_X } from '@/composables/diagrams/layoutConfig'
import { inferMindMapThemeIdFromNodes, resolveActiveMindMapThemeId } from '@/config/mindMapThemes'
import { i18n } from '@/i18n'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { readMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import {
  MINDMAP_NODE_UID_DATA_KEY,
  collectMindMapNodeUids,
  ensureMindMapBranchUid,
  findNodeIdByMindMapUid,
  readMindMapNodeUid,
  rebindMindMapBranchUidsForPaste,
} from '@/utils/mindMapNodeUid'
import { markMindMapInlineEditStage } from '@/utils/mindMapInlineEditDebug'
import {
  recordMindMapSiblingInsertAttempt,
  recordMindMapSiblingInsertFailure,
  recordMindMapSiblingInsertSuccess,
} from '@/utils/mindMapSiblingDebug'
import {
  applyMindMapIncrementalDeleteLayout,
  applyMindMapIncrementalSiblingYPreserve,
  applyMindMapIncrementalTopLevelSiblingLayout,
} from '@/utils/mindMapSideStacking'
import {
  debugMindMapSubgraphMergeLookup,
  isMindMapSubgraphDebugEnabled,
  mindMapSubgraphDebug,
  mindMapSubgraphDebugError,
} from '@/utils/mindMapSubgraphDebug'
import {
  type MindMapBranchSpec,
  mergeGeneratedBranchesIntoSpec,
} from '@/utils/mindMapSubgraphMerge'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

import { useInlineRecommendationsStore } from '../inlineRecommendations'
import { useMindMapSubgraphPreviewStore } from '../mindMapSubgraphPreview'
import {
  distributeBranchesClockwise,
  findBranchByNodeId,
  loadMindMapSpec,
  mindMapBranchesClockwiseOrder,
  nodesAndConnectionsToMindMapSpec,
  rebalanceMindMapBranchesIfLeftOnly,
} from '../specLoader'
import type { SpecLoaderResult } from '../specLoader/types'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { emitCtxEvent, getMindMapCurveExtents } from './events'
import {
  getMindMapCollapsedNodeIds,
  getMindMapCollapsedPaths,
  isMindMapPathCollapsed,
  mindMapNodeHasChildren,
  pruneMindMapCollapsedPaths,
  remapMindMapCollapsedPathsAfterReload,
  remapMindMapMeasuredDimensionsAfterReload,
  remapMindMapNodeIdAfterReload,
  remapMindMapNodeIdsAfterReload,
  setMindMapCollapsedPaths,
} from './mindMapCollapse'
import { recalculateMindMapV2ColumnPositions } from './mindMapLayout'
import { insertMindMapSiblingInPlace } from './mindMapSiblingInsert'
import {
  findNodeIdByPathKey,
  mergeMindMapReloadStyles,
  mindMapNodePathKey,
} from './mindMapStylePreservation'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import type { DiagramContext } from './types'

function defaultNewNodeText(): string {
  return String(i18n.global.t('diagram.editable.placeholder')).replace(/[….]{1,3}$/u, '')
}

function defaultNewChildText(): string {
  return String(i18n.global.t('diagram.newChild'))
}

function defaultLegacyBranchWithChildren(
  text: string,
  childText = defaultNewChildText()
): { text: string; children: { text: string }[] } {
  return {
    text,
    children: [{ text: `${childText} 1` }, { text: `${childText} 2` }],
  }
}

/** Legacy canvas: new top-level branches include two default children; v2: text only. */
function newTopLevelMindMapBranchSpec(
  text: string,
  childText = defaultNewChildText()
): { text: string; children?: { text: string }[] } {
  if (readMindMapV2VisualDesignActive()) {
    return { text }
  }
  return defaultLegacyBranchWithChildren(text, childText)
}

function resolvePathKeyForBranchSpec(
  branchSpec: { text: string; children?: { text: string }[] },
  rightBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['rightBranches'],
  leftBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['leftBranches']
): string | null {
  const rightIdx = rightBranches.indexOf(branchSpec)
  if (rightIdx >= 0) return `r/${rightIdx}`
  const leftIdx = leftBranches.indexOf(branchSpec)
  if (leftIdx >= 0) return `l/${leftIdx}`
  return null
}

/**
 * Retain DOM-measured widths/heights across a tree rebuild by remapping to new
 * node ids, then seeding any gaps from build-time estimates so layout does not
 * fall back to defaults and jump when the first post-edit measurement arrives.
 */
function retainMeasuredDimensions(
  ctx: DiagramContext,
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  scheduleRecalc = true
): void {
  const { widths, heights } = remapMindMapMeasuredDimensionsAfterReload(
    ctx.mindMapNodeWidths.value,
    ctx.mindMapNodeHeights.value,
    oldNodes,
    oldConnections,
    newNodes,
    newConnections
  )
  ctx.mindMapNodeWidths.value = widths
  ctx.mindMapNodeHeights.value = heights
  if (scheduleRecalc) {
    ctx.scheduleMindMapRecalc()
  }
}

function getMindMapParentId(connections: Connection[], nodeId: string): string | null {
  return connections.find((c) => c.target === nodeId)?.source ?? null
}

function computeSiblingPathKey(
  nodeId: string,
  insertIndex: number,
  connections: Connection[]
): string | null {
  const parentId = getMindMapParentId(connections, nodeId)
  if (!parentId || parentId === 'topic') {
    const side = nodeId.startsWith('branch-l-') ? 'l' : 'r'
    return `${side}/${insertIndex}`
  }
  const parentPath = mindMapNodePathKey(parentId, connections)
  if (!parentPath) return null
  return `${parentPath}/${insertIndex}`
}

const MIND_MAP_INLINE_EDIT_MAX_ATTEMPTS = 80
const MIND_MAP_INLINE_EDIT_RETRY_MS = 40
/** Allow Vue Flow remount selection echo; after this, user selection wins. */
const MIND_MAP_PENDING_EDIT_REMOUNT_ECHO_MS = 400
/** Force-reselect only while hosts settle; then yield if selection moved. */
const MIND_MAP_PENDING_EDIT_SELECTION_GUARD_ATTEMPTS = 12

let mindMapInlineEditRetryGeneration = 0
let mindMapPendingEditArmedAtMs = 0
let mindMapPendingEditPointerCleanup: (() => void) | null = null

const MIND_MAP_PENDING_EDIT_EPHEMERAL_UI_SELECTOR = [
  '.el-notification',
  '.el-message',
  '.el-overlay',
  '.el-message-box',
  '.el-loading-mask',
  '.dark-alert-notification',
].join(', ')

function detachMindMapPendingEditPointerGuard(): void {
  if (!mindMapPendingEditPointerCleanup) return
  mindMapPendingEditPointerCleanup()
  mindMapPendingEditPointerCleanup = null
}

/** Abort pending post-add inline-edit retries (navigation / store reset / user intent). */
export function cancelMindMapPendingInlineEdit(
  ctx: DiagramContext,
  reason = 'cancelMindMapPendingInlineEdit'
): void {
  const previousPending = ctx.mindMapPendingEditNodeId.value
  mindMapInlineEditRetryGeneration += 1
  ctx.mindMapPendingEditNodeId.value = null
  mindMapPendingEditArmedAtMs = 0
  detachMindMapPendingEditPointerGuard()
  if (previousPending) {
    const stage =
      reason === 'focus-tick-success' ? 'pending:open-phase-done' : 'pending:cancel'
    markMindMapInlineEditStage(stage, {
      nodeId: previousPending,
      editingId: ctx.mindMapEditingNodeId.value,
      generation: mindMapInlineEditRetryGeneration,
      reason,
    })
  }
}

/** Begin / update store-owned mind-map inline-edit session (survives remount). */
export function setMindMapEditingNodeId(ctx: DiagramContext, nodeId: string | null): void {
  ctx.mindMapEditingNodeId.value = nodeId
}

/** Clear store-owned edit session; optional nodeId only clears when it matches. */
export function clearMindMapEditingNodeId(ctx: DiagramContext, nodeId?: string): void {
  if (nodeId != null && ctx.mindMapEditingNodeId.value !== nodeId) return
  ctx.mindMapEditingNodeId.value = null
}

/**
 * After remount-echo grace, yield sticky post-add edit when selection leaves the
 * pending node (sidebar / Vue Flow click). During grace, tryFocus may reassert.
 */
export function releaseMindMapPendingInlineEditIfSelectionMoved(
  ctx: DiagramContext,
  nextSelectedIds: readonly string[]
): void {
  const pending = ctx.mindMapPendingEditNodeId.value
  if (!pending) return
  if (nextSelectedIds.includes(pending)) return
  if (Date.now() - mindMapPendingEditArmedAtMs < MIND_MAP_PENDING_EDIT_REMOUNT_ECHO_MS) {
    return
  }
  cancelMindMapPendingInlineEdit(ctx)
}

function isMindMapPendingEditEphemeralTarget(target: EventTarget | null): boolean {
  return target instanceof Element && !!target.closest(MIND_MAP_PENDING_EDIT_EPHEMERAL_UI_SELECTOR)
}

function attachMindMapPendingEditPointerGuard(
  ctx: DiagramContext,
  nodeId: string,
  generation: number
): void {
  detachMindMapPendingEditPointerGuard()

  const onPointerDown = (event: Event): void => {
    if (generation !== mindMapInlineEditRetryGeneration) {
      detachMindMapPendingEditPointerGuard()
      return
    }
    if (ctx.mindMapPendingEditNodeId.value !== nodeId) {
      detachMindMapPendingEditPointerGuard()
      return
    }
    if (isMindMapPendingEditEphemeralTarget(event.target)) return

    const target = event.target
    if (!(target instanceof Element)) return

    const nodeEl = target.closest('.vue-flow__node')
    if (nodeEl instanceof HTMLElement) {
      const clickedId = nodeEl.getAttribute('data-id')
      if (clickedId && clickedId !== nodeId) {
        // User picked another branch — stop sticky reselect immediately.
        cancelMindMapPendingInlineEdit(ctx)
      }
      return
    }

    if (target.closest('.vue-flow__pane, .vue-flow')) {
      cancelMindMapPendingInlineEdit(ctx)
    }
  }

  document.addEventListener('pointerdown', onPointerDown, true)
  mindMapPendingEditPointerCleanup = () => {
    document.removeEventListener('pointerdown', onPointerDown, true)
  }
}

function escapeMindMapNodeSelectorId(nodeId: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(nodeId)
  }
  return nodeId.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
}

/** Select a mind-map node and notify listeners / Vue Flow. */
function selectMindMapNode(ctx: DiagramContext, nodeId: string): void {
  ctx.selectedConnectionId.value = null
  ctx.selectedNodes.value = [nodeId]
  emitCtxEvent(ctx, 'diagram:selection_changed', { selectedNodes: [nodeId] })
}

function clearMindMapPendingEditIfCurrent(ctx: DiagramContext, nodeId: string): void {
  if (ctx.mindMapPendingEditNodeId.value !== nodeId) return
  // Bump generation so in-flight tryFocus timers cannot resurrect the open loop.
  mindMapInlineEditRetryGeneration += 1
  ctx.mindMapPendingEditNodeId.value = null
  mindMapPendingEditArmedAtMs = 0
  detachMindMapPendingEditPointerGuard()
  markMindMapInlineEditStage('pending:cleared', {
    nodeId,
    editingId: ctx.mindMapEditingNodeId.value,
    generation: mindMapInlineEditRetryGeneration,
  })
}

function requestMindMapNodeInlineEdit(ctx: DiagramContext, nodeId: string): void {
  mindMapInlineEditRetryGeneration += 1
  const generation = mindMapInlineEditRetryGeneration
  mindMapPendingEditArmedAtMs = Date.now()
  // Pending only here. Do NOT set mindMapEditingNodeId yet — that flips V2
  // isEditing on first paint so ResizeObserver measures the wide <input> and
  // layout places/sizes the branch wrong. Session is set in startEditing once
  // the display-mode measure has landed (or below once focus is stable).
  ctx.mindMapPendingEditNodeId.value = nodeId
  markMindMapInlineEditStage('pending:arm', {
    nodeId,
    editingId: ctx.mindMapEditingNodeId.value,
    generation,
    selectedId: ctx.selectedNodes.value[0] ?? null,
  })
  // Keep selection on the node we are about to edit (Enter add → new branch).
  selectMindMapNode(ctx, nodeId)
  attachMindMapPendingEditPointerGuard(ctx, nodeId, generation)
  let attempts = 0

  const finishPending = (): void => {
    if (generation !== mindMapInlineEditRetryGeneration) return
    clearMindMapPendingEditIfCurrent(ctx, nodeId)
  }

  const scheduleRetry = (): void => {
    if (attempts < MIND_MAP_INLINE_EDIT_MAX_ATTEMPTS) {
      setTimeout(tryFocus, MIND_MAP_INLINE_EDIT_RETRY_MS)
      return
    }
    markMindMapInlineEditStage('pending:max-attempts', {
      nodeId,
      generation,
      attempt: attempts,
      editingId: ctx.mindMapEditingNodeId.value,
    })
    // Exhausted retries — drop pending so a stuck id cannot steal later clicks.
    // Keep mindMapEditingNodeId so remount / write-back can still reopen edit.
    finishPending()
  }

  const tryFocus = (): void => {
    if (generation !== mindMapInlineEditRetryGeneration) return
    if (ctx.mindMapPendingEditNodeId.value !== nodeId) return
    attempts += 1
    markMindMapInlineEditStage('pending:tryFocus', {
      nodeId,
      generation,
      attempt: attempts,
      selectedId: ctx.selectedNodes.value[0] ?? null,
      editingId: ctx.mindMapEditingNodeId.value,
    })
    // Vue Flow can briefly echo the previous selection when nodes remount.
    // Force-reselect only during settle; after that honor selection (do not
    // cancel pending — releaseMindMapPendingInlineEditIfSelectionMoved owns that).
    if (ctx.selectedNodes.value[0] !== nodeId) {
      markMindMapInlineEditStage('pending:selection-drift', {
        nodeId,
        generation,
        attempt: attempts,
        selectedId: ctx.selectedNodes.value[0] ?? null,
      })
      if (attempts <= MIND_MAP_PENDING_EDIT_SELECTION_GUARD_ATTEMPTS) {
        selectMindMapNode(ctx, nodeId)
      } else {
        scheduleRetry()
        return
      }
    }

    const host = document.querySelector(
      `.vue-flow__node[data-id="${escapeMindMapNodeSelectorId(nodeId)}"] .inline-editable-text`
    )

    if (host) {
      markMindMapInlineEditStage('pending:host-found', {
        nodeId,
        generation,
        attempt: attempts,
      })
      ctx.viewBus.emit('node:edit_requested', { nodeId })
      markMindMapInlineEditStage('pending:edit_requested', {
        nodeId,
        generation,
        attempt: attempts,
        source: 'tryFocus',
      })
      const input = host.querySelector('.inline-edit-input') as HTMLInputElement | null
      // Session already open (startEditing ran): write-back may have stolen focus.
      // Refocus once, then end open-phase — do not spam 80 edit_requested retries.
      if (ctx.mindMapEditingNodeId.value === nodeId) {
        if (input && document.activeElement !== input && typeof input.focus === 'function') {
          input.focus()
          if (typeof input.select === 'function') {
            input.select()
          }
        }
        markMindMapInlineEditStage('pending:focus-stable', {
          nodeId,
          generation,
          attempt: attempts,
          editingId: ctx.mindMapEditingNodeId.value,
          focused: !!input && document.activeElement === input,
          reason: 'session-open-end-retries',
        })
        finishPending()
        return
      }
      // Pending is open-phase only. Remount recovery is owned by
      // mindMapEditingNodeId. Clear pending once focus is stable.
      if (input && document.activeElement === input) {
        requestAnimationFrame(() => {
          if (generation !== mindMapInlineEditRetryGeneration) return
          if (ctx.mindMapPendingEditNodeId.value !== nodeId) return
          const stillInput = document.querySelector(
            `.vue-flow__node[data-id="${escapeMindMapNodeSelectorId(nodeId)}"] .inline-edit-input`
          ) as HTMLInputElement | null
          if (stillInput && document.activeElement === stillInput) {
            if (ctx.mindMapEditingNodeId.value !== nodeId) {
              ctx.mindMapEditingNodeId.value = nodeId
            }
            markMindMapInlineEditStage('pending:focus-stable', {
              nodeId,
              generation,
              attempt: attempts,
              editingId: ctx.mindMapEditingNodeId.value,
            })
            finishPending()
            return
          }
          scheduleRetry()
        })
        return
      }
      markMindMapInlineEditStage('pending:awaiting-input', {
        nodeId,
        generation,
        attempt: attempts,
        hasInput: !!input,
        focused: document.activeElement === input,
        editingId: ctx.mindMapEditingNodeId.value,
      })
      scheduleRetry()
      return
    }

    markMindMapInlineEditStage('pending:host-missing', {
      nodeId,
      generation,
      attempt: attempts,
    })
    if (attempts >= MIND_MAP_INLINE_EDIT_MAX_ATTEMPTS) {
      ctx.viewBus.emit('node:edit_requested', { nodeId })
      markMindMapInlineEditStage('pending:max-attempts', {
        nodeId,
        generation,
        attempt: attempts,
        reason: 'host-missing',
      })
      // Last resort: drop pending so a stuck id cannot steal later edits.
      finishPending()
      return
    }
    requestAnimationFrame(tryFocus)
  }

  requestAnimationFrame(() => requestAnimationFrame(tryFocus))
}

function selectAndEditByPathKey(
  ctx: DiagramContext,
  nodes: DiagramNode[],
  connections: Connection[],
  pathKey: string | null,
  scheduleRecalc = true
): void {
  if (!pathKey) return
  const nodeId = findNodeIdByPathKey(nodes, connections, pathKey)
  if (!nodeId) return
  selectMindMapNode(ctx, nodeId)
  if (scheduleRecalc) {
    // Same as in-place sibling: settle positions before arming post-add edit.
    if (ctx.writeBackMindMapV2LayoutFromComputed) {
      ctx.writeBackMindMapV2LayoutFromComputed()
    }
    ctx.scheduleMindMapRecalc()
  }
  requestMindMapNodeInlineEdit(ctx, nodeId)
}

type CommitMindMapReloadOptions = {
  skipMindMapRecalc?: boolean
  /**
   * Hold the v2 layout computed on store XY while heights/nodes swap, run the
   * same engine sync into the store, then briefly preserve Y — first paint
   * matches post-recalc (no off-then-correct flash).
   */
  syncV2LayoutBeforeShow?: boolean
}

/** Re-arm sticky Y after commitMindMapReload cleared it (two frames). */
function armMindMapPreserveIncomingYBriefly(ctx: DiagramContext): void {
  ctx.mindMapPreserveIncomingY.value = true
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        ctx.mindMapPreserveIncomingY.value = false
      })
    })
    return
  }
  ctx.mindMapPreserveIncomingY.value = false
}

function commitMindMapReloadWithSelect(
  ctx: DiagramContext,
  result: SpecLoaderResult,
  selectPathKey: string | null,
  historyLabel: string,
  options?: CommitMindMapReloadOptions
): boolean {
  if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return false
  commitMindMapReload(ctx, result, options)
  ctx.pushHistory(historyLabel)
  emitCtxEvent(ctx, 'diagram:node_added', { node: null })
  selectAndEditByPathKey(
    ctx,
    result.nodes,
    result.connections,
    selectPathKey,
    !options?.skipMindMapRecalc
  )
  return true
}

function commitMindMapReload(
  ctx: DiagramContext,
  result: SpecLoaderResult,
  options?: CommitMindMapReloadOptions
): void {
  if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return

  // Full tree rebuild owns Y again — drop in-place Enter preserve.
  ctx.mindMapPreserveIncomingY.value = false
  ctx.mindMapPreserveIncomingYNodeId.value = null

  const v2Visuals = readMindMapV2VisualDesignActive()
  const skipRecalc = options?.skipMindMapRecalc === true
  const syncV2 = options?.syncV2LayoutBeforeShow === true && v2Visuals
  const holdBulk = syncV2

  if (holdBulk) {
    ctx.mindMapBulkLoading.value = true
  }

  if (v2Visuals && !ctx.data.value._mindmap_theme) {
    const inferred = inferMindMapThemeIdFromNodes(ctx.data.value.nodes)
    if (inferred) ctx.data.value._mindmap_theme = inferred
  }

  const mergedNodeStyles = mergeMindMapReloadStyles(
    ctx.data.value.nodes,
    ctx.data.value.connections,
    result.nodes,
    result.connections,
    ctx.data.value._node_styles,
    resolveActiveMindMapThemeId(ctx.data.value),
    ctx.data.value._mindmap_diagram_style,
    remapMindMapNodeIdAfterReload
  )

  const oldNodes = ctx.data.value.nodes
  const oldConnections = ctx.data.value.connections

  retainMeasuredDimensions(
    ctx,
    oldNodes,
    oldConnections,
    result.nodes,
    result.connections,
    !skipRecalc
  )

  const previousSelected = [...ctx.selectedNodes.value]
  const previousPendingEdit = ctx.mindMapPendingEditNodeId.value
  const previewStore = useMindMapSubgraphPreviewStore()

  ctx.data.value.nodes = result.nodes
  ctx.data.value.connections = result.connections
  ctx.data.value._node_styles = mergedNodeStyles

  if (syncV2 && (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map')) {
    const connections = ctx.data.value.connections ?? []
    const collapsedPaths = getMindMapCollapsedPaths(ctx.data.value)
    const collapsedNodeIds = getMindMapCollapsedNodeIds(
      ctx.data.value.nodes,
      connections,
      collapsedPaths
    )
    const diagramStyleId =
      typeof ctx.data.value._mindmap_diagram_style === 'string'
        ? ctx.data.value._mindmap_diagram_style
        : undefined
    const laidOut = recalculateMindMapV2ColumnPositions(
      ctx.data.value.nodes,
      ctx.mindMapTopicActualWidth.value,
      ctx.mindMapNodeWidths.value,
      ctx.mindMapNodeHeights.value,
      connections,
      collapsedNodeIds,
      diagramStyleId
    )
    ctx.data.value.nodes = laidOut.nodes
    ctx.mindMapTopicBranchGaps.value = laidOut.gaps
  }

  if (!skipRecalc && (ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map')) {
    ctx.mindMapRecalcTrigger.value += 1
    ctx.scheduleMindMapRecalc()
  }

  if (v2Visuals) {
    const collapsedBefore = ctx.data.value._collapsed_paths ?? []
    const remapped = remapMindMapCollapsedPathsAfterReload(
      oldNodes,
      oldConnections,
      result.nodes,
      result.connections,
      collapsedBefore
    )
    const pruned = pruneMindMapCollapsedPaths(
      ctx.data.value.nodes,
      ctx.data.value.connections ?? [],
      remapped
    )
    setMindMapCollapsedPaths(ctx.data.value as Record<string, unknown>, pruned)
  }

  ctx.selectedNodes.value = remapMindMapNodeIdsAfterReload(
    previousSelected,
    oldNodes,
    oldConnections,
    ctx.data.value.nodes,
    ctx.data.value.connections ?? []
  )
  if (previousPendingEdit) {
    ctx.mindMapPendingEditNodeId.value = remapMindMapNodeIdAfterReload(
      previousPendingEdit,
      oldNodes,
      oldConnections,
      ctx.data.value.nodes,
      ctx.data.value.connections ?? []
    )
  }
  previewStore.remapGeneratingNodeIds((oldId) =>
    remapMindMapNodeIdAfterReload(
      oldId,
      oldNodes,
      oldConnections,
      ctx.data.value?.nodes ?? result.nodes,
      ctx.data.value?.connections ?? result.connections
    )
  )

  if (holdBulk) {
    ctx.mindMapBulkLoading.value = false
  }
  if (syncV2) {
    armMindMapPreserveIncomingYBriefly(ctx)
  }
}

export function useMindMapOpsSlice(ctx: DiagramContext) {
  const { type, data, selectedNodes, mindMapCurveExtentBaseline } = ctx

  function addMindMapBranch(
    side: 'left' | 'right',
    text = defaultNewNodeText(),
    childText = defaultNewChildText()
  ): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (readMindMapV2VisualDesignActive()) {
      return addMindMapBranchOnSide(side, text)
    }
    return addMindMapBranchClockwise(text, childText)
  }

  function addMindMapBranchClockwise(
    text = defaultNewNodeText(),
    childText = defaultNewChildText()
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const newBranch = newTopLevelMindMapBranchSpec(text, childText)

    const allBranches = mindMapBranchesClockwiseOrder(spec.rightBranches, spec.leftBranches)
    allBranches.push(newBranch)
    const { rightBranches, leftBranches } = distributeBranchesClockwise(allBranches)
    const pathKey = resolvePathKeyForBranchSpec(newBranch, rightBranches, leftBranches)

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches,
      rightBranches,
      preserveLeftRight: true,
    })
    return commitMindMapReloadWithSelect(ctx, result, pathKey, 'Add branch')
  }

  function addMindMapBranchOnSide(side: 'left' | 'right', text = defaultNewNodeText()): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const newBranch = { text }
    const pathKey =
      side === 'left' ? `l/${spec.leftBranches.length}` : `r/${spec.rightBranches.length}`

    if (side === 'left') {
      spec.leftBranches.push(newBranch)
    } else {
      spec.rightBranches.push(newBranch)
    }

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    return commitMindMapReloadWithSelect(ctx, result, pathKey, 'Add branch')
  }

  function addMindMapChild(parentNodeId: string, text = defaultNewNodeText()): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    const found = findBranchByNodeId(
      spec.rightBranches,
      spec.leftBranches,
      parentNodeId,
      connections
    )
    if (!found) return false

    const { branch } = found
    if (!branch.children) {
      branch.children = []
    }
    branch.children.push({ text })
    const parentPath = mindMapNodePathKey(parentNodeId, connections)
    const pathKey = parentPath ? `${parentPath}/${branch.children.length - 1}` : null

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    const ok = commitMindMapReloadWithSelect(ctx, result, pathKey, 'Add child')
    if (ok && pathKey) {
      const newChildId = findNodeIdByPathKey(result.nodes, result.connections, pathKey)
      if (newChildId) {
        // Pan-only: keep new child in the central ~75% of the canvas (no zoom-fit).
        ctx.viewBus.emit('view:ensure_node_visible_requested', {
          nodeId: newChildId,
          animate: true,
        })
      }
    }
    return ok
  }

  function removeMindMapNodes(nodeIds: string[]): number {
    if (isDiagramPresentationReadOnly(ctx)) return 0
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return 0
    if (!data.value?.nodes || !data.value?.connections) return 0

    const connections = data.value.connections
    const beforeNodes = data.value.nodes
    const beforeConnections = connections
    const topicY = beforeNodes.find((node) => node.id === 'topic')?.position?.y
    const spec = nodesAndConnectionsToMindMapSpec(beforeNodes, connections)
    const idsToRemove = new Set(nodeIds.filter((id) => id.startsWith('branch-')))

    if (collabForeignLockBlocksAnyId(ctx, idsToRemove)) {
      emitCollabDeleteBlocked()
      return 0
    }

    const toRemoveWithParent: {
      nodeId: string
      parentArray: { text: string; children?: unknown[] }[]
      indexInParent: number
    }[] = []
    idsToRemove.forEach((nodeId) => {
      const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, nodeId, connections)
      if (found) {
        toRemoveWithParent.push({
          nodeId,
          parentArray: found.parentArray,
          indexInParent: found.indexInParent,
        })
      }
    })

    const depth = (id: string) => parseInt(id.split('-')[2] ?? '0', 10)
    toRemoveWithParent.sort((a, b) => {
      const dA = depth(a.nodeId)
      const dB = depth(b.nodeId)
      if (dA !== dB) return dB - dA
      return b.indexInParent - a.indexInParent
    })
    toRemoveWithParent.forEach(({ parentArray, indexInParent }) => {
      parentArray.splice(indexInParent, 1)
    })

    const deletedCount = toRemoveWithParent.length
    if (deletedCount === 0) return 0

    const deletedNodeIds = toRemoveWithParent.map((item) => item.nodeId)
    // Deleting every right L1 leaves a left-only map (no structure mode for that).
    // Redistribute clockwise so survivors split across both sides again.
    const balanced = rebalanceMindMapBranchesIfLeftOnly(spec.leftBranches, spec.rightBranches)
    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: balanced.leftBranches,
      rightBranches: balanced.rightBranches,
      preserveLeftRight: true,
    })

    if (balanced.redistributed) {
      commitMindMapReload(ctx, result)
      // Survivor layout ids change side/index; drop inline-rec state keyed by old ids.
      useInlineRecommendationsStore().invalidateAll()
    } else {
      const collapsedPaths = getMindMapCollapsedPaths(data.value)
      const collapsedNodeIds = getMindMapCollapsedNodeIds(
        beforeNodes,
        beforeConnections,
        collapsedPaths
      )
      const incremental = applyMindMapIncrementalDeleteLayout(
        beforeNodes,
        beforeConnections,
        result.nodes,
        result.connections,
        {
          deletedNodeIds,
          topicY: typeof topicY === 'number' ? topicY : undefined,
          nodeHeights: ctx.mindMapNodeHeights.value,
          collapsedNodeIds,
          diagramStyleId:
            typeof data.value._mindmap_diagram_style === 'string'
              ? data.value._mindmap_diagram_style
              : undefined,
        }
      )
      commitMindMapReload(
        ctx,
        { ...result, nodes: incremental.nodes },
        {
          skipMindMapRecalc: incremental.usedIncremental,
          // Same engine as the v2 display computed, applied before first paint.
          syncV2LayoutBeforeShow: incremental.usedIncremental,
        }
      )
    }

    nodeIds.forEach((id) => {
      ctx.clearCustomPosition(id)
      ctx.clearNodeStyle(id)
      ctx.removeFromSelection(id)
    })
    ctx.pushHistory('Delete nodes')
    emitCtxEvent(ctx, 'diagram:nodes_deleted', { nodeIds })
    return deletedCount
  }

  function getMindMapDescendantIds(rootNodeId: string): Set<string> {
    const connections = data.value?.connections ?? []
    const childrenMap = new Map<string, string[]>()
    connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })
    const result = new Set<string>([rootNodeId])
    function collect(id: string): void {
      for (const childId of childrenMap.get(id) ?? []) {
        result.add(childId)
        collect(childId)
      }
    }
    collect(rootNodeId)
    return result
  }

  function moveMindMapBranch(
    branchNodeId: string,
    targetType: 'topic' | 'child' | 'before' | 'after' | 'sibling',
    targetId?: string,
    _targetIndex?: number,
    cursorFlowX?: number
  ): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (branchNodeId === 'topic') return false

    const centerX = DEFAULT_CENTER_X
    const extentsBefore = getMindMapCurveExtents(data.value.nodes, centerX)

    if (mindMapCurveExtentBaseline.value == null) {
      mindMapCurveExtentBaseline.value = { ...extentsBefore }
    }

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    const sourceFound = findBranchByNodeId(
      spec.rightBranches,
      spec.leftBranches,
      branchNodeId,
      connections
    )
    if (!sourceFound) return false

    const { branch, parentArray, indexInParent } = sourceFound
    const descendantIds = getMindMapDescendantIds(branchNodeId)

    if ((targetType === 'child' || targetType === 'before' || targetType === 'after') && targetId) {
      if (descendantIds.has(targetId)) return false
    }

    if (targetType === 'topic') {
      parentArray.splice(indexInParent, 1)
      const useLeft = cursorFlowX !== undefined && cursorFlowX < DEFAULT_CENTER_X
      if (useLeft) {
        spec.leftBranches.push(branch)
      } else {
        spec.rightBranches.push(branch)
      }
    } else if (targetType === 'child' && targetId) {
      const targetFound = findBranchByNodeId(
        spec.rightBranches,
        spec.leftBranches,
        targetId,
        connections
      )
      if (!targetFound) return false
      parentArray.splice(indexInParent, 1)
      if (!targetFound.branch.children) targetFound.branch.children = []
      targetFound.branch.children.push(branch)
    } else if ((targetType === 'before' || targetType === 'after') && targetId) {
      const targetFound = findBranchByNodeId(
        spec.rightBranches,
        spec.leftBranches,
        targetId,
        connections
      )
      if (!targetFound) return false

      const [removed] = parentArray.splice(indexInParent, 1)
      const targetParentArray = targetFound.parentArray
      let insertIdx =
        targetType === 'before' ? targetFound.indexInParent : targetFound.indexInParent + 1

      if (parentArray === targetParentArray && indexInParent < insertIdx) {
        insertIdx -= 1
      }
      targetParentArray.splice(insertIdx, 0, removed)
    } else if (targetType === 'sibling' && targetId !== undefined) {
      const targetFound = findBranchByNodeId(
        spec.rightBranches,
        spec.leftBranches,
        targetId,
        connections
      )
      if (!targetFound) return false
      if (descendantIds.has(targetId)) return false

      const targetBranch = targetFound.branch
      const targetParentArray = targetFound.parentArray
      const targetIdx = targetFound.indexInParent

      const isSameParent = parentArray === targetParentArray

      if (isSameParent) {
        const [removed] = parentArray.splice(indexInParent, 1)
        const adjustedTargetIdx = indexInParent < targetIdx ? targetIdx - 1 : targetIdx
        const [removedTarget] = parentArray.splice(adjustedTargetIdx, 1)
        if (indexInParent < targetIdx) {
          parentArray.splice(indexInParent, 0, removedTarget)
          parentArray.splice(targetIdx, 0, removed)
        } else {
          parentArray.splice(targetIdx, 0, removed)
          parentArray.splice(indexInParent, 0, removedTarget)
        }
      } else {
        parentArray.splice(indexInParent, 1)
        targetParentArray.splice(targetIdx, 1)
        parentArray.splice(indexInParent, 0, targetBranch)
        targetParentArray.splice(targetIdx, 0, branch)
      }
    } else {
      return false
    }

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    commitMindMapReload(ctx, result)
    selectedNodes.value = []
    ctx.selectedConnectionId.value = null
    ctx.pushHistory('Move branch')
    emitCtxEvent(ctx, 'diagram:operation_completed', { operation: 'move_branch' })
    // Fit via branch_moved only — do not emit diagram:loaded (that resets palette/AI/fit flags).
    ctx.viewBus.emit('diagram:branch_moved', {})

    const targetDescendantIds =
      (targetType === 'sibling' && targetId) || (targetType === 'child' && targetId)
        ? getMindMapDescendantIds(targetId)
        : new Set<string>()
    ;[...descendantIds, ...targetDescendantIds].forEach((id) => {
      useInlineRecommendationsStore().invalidateForNode(id)
    })

    return true
  }

  function applyMindMapSpecReload(
    topic: string,
    leftBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['leftBranches'],
    rightBranches: ReturnType<typeof nodesAndConnectionsToMindMapSpec>['rightBranches'],
    historyLabel: string,
    selectPathKey: string | null = null
  ): boolean {
    const result = loadMindMapSpec({
      topic,
      leftBranches,
      rightBranches,
      preserveLeftRight: true,
    })
    return commitMindMapReloadWithSelect(ctx, result, selectPathKey, historyLabel)
  }

  function getMindMapStructureMode(): 'balanced' | 'right' {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return 'balanced'
    if (!data.value?.nodes || !data.value?.connections) return 'balanced'
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    return spec.leftBranches.length === 0 ? 'right' : 'balanced'
  }

  function setMindMapStructureMode(mode: 'balanced' | 'right'): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const allBranches = mindMapBranchesClockwiseOrder(spec.rightBranches, spec.leftBranches)

    if (mode === 'right') {
      return applyMindMapSpecReload(spec.topic, [], allBranches, 'Structure: right')
    }

    const { rightBranches, leftBranches } = distributeBranchesClockwise(allBranches)
    return applyMindMapSpecReload(spec.topic, leftBranches, rightBranches, 'Structure: balanced')
  }

  function commitMindMapSiblingInPlace(
    inserted: NonNullable<ReturnType<typeof insertMindMapSiblingInPlace>>,
    historyLabel: string
  ): boolean {
    if (!data.value?.nodes || !data.value?.connections) return false

    data.value.nodes = inserted.nodes
    data.value.connections = inserted.connections
    ctx.mindMapNodeWidths.value = {
      ...ctx.mindMapNodeWidths.value,
      [inserted.newNodeId]: inserted.estimatedWidth,
    }
    ctx.mindMapNodeHeights.value = {
      ...ctx.mindMapNodeHeights.value,
      [inserted.newNodeId]: inserted.estimatedHeight,
    }
    // Style is minted on the node in insertMindMapSiblingInPlace; mirror into SoT map.
    data.value._node_styles = {
      ...(data.value._node_styles || {}),
      [inserted.newNodeId]: { ...inserted.seededStyle },
    }

    if (inserted.isTopLevel) {
      // Keep preserve across measure/edit-end (full restack caused delayed L1 shift).
      // Cleared on collapse/expand/style switch so those ops can full-restack.
      ctx.mindMapPreserveIncomingY.value = true
      ctx.mindMapPreserveIncomingYNodeId.value = inserted.newNodeId
    }

    const newNode = data.value.nodes.find((node) => node.id === inserted.newNodeId) ?? null
    ctx.pushHistory(historyLabel)
    emitCtxEvent(ctx, 'diagram:node_added', newNode)

    // Sync write-back first so the big position merge happens before edit starts.
    // Then arm pending edit; scheduled recalc is usually a no-op merge + trigger.
    if (ctx.writeBackMindMapV2LayoutFromComputed) {
      ctx.writeBackMindMapV2LayoutFromComputed()
    }
    ctx.scheduleMindMapRecalc()
    requestMindMapNodeInlineEdit(ctx, inserted.newNodeId)
    return true
  }

  /**
   * Insert a sibling in-place (v2) or via reload (legacy).
   * Optional `at` selects absolute index / after_node for Kitty + paste.
   */
  function addMindMapSibling(
    nodeId: string,
    text = defaultNewNodeText(),
    position: 'above' | 'below' = 'below',
    at?: { insertIndex?: number; afterNodeId?: string; parentId?: string }
  ): boolean {
    recordMindMapSiblingInsertAttempt({
      nodeId,
      text,
      position,
      at,
      selected: selectedNodes.value.slice(),
      v2: readMindMapV2VisualDesignActive(),
      presentationReadOnly: isDiagramPresentationReadOnly(ctx),
      type: type.value,
    })
    if (isDiagramPresentationReadOnly(ctx)) {
      recordMindMapSiblingInsertFailure('presentation_read_only', { nodeId })
      return false
    }
    if (type.value !== 'mindmap' && type.value !== 'mind_map') {
      recordMindMapSiblingInsertFailure('not_mindmap', { type: type.value, nodeId })
      return false
    }
    if (!data.value?.nodes || !data.value?.connections) {
      recordMindMapSiblingInsertFailure('no_diagram_data', { nodeId })
      return false
    }
    if (nodeId === 'topic' && at?.parentId == null && at?.insertIndex == null) {
      recordMindMapSiblingInsertFailure('topic_without_insert_at', { nodeId, at })
      return false
    }

    // v2: mint one id + edge; connection order is SoT — no loadMindMapSpec.
    if (readMindMapV2VisualDesignActive()) {
      // Stale free-index ids after an accidental library reload leave selection
      // pointing at a node with no parent edge — recover another valid selection.
      let anchorNodeId = nodeId === 'topic' ? undefined : nodeId
      const diagramConnections = data.value.connections
      if (anchorNodeId && !diagramConnections.some((conn) => conn.target === anchorNodeId)) {
        const fallback = selectedNodes.value.find(
          (id) =>
            id !== anchorNodeId &&
            id !== 'topic' &&
            diagramConnections.some((conn) => conn.target === id)
        )
        if (fallback) {
          recordMindMapSiblingInsertAttempt({
            stage: 'stale_anchor_recovered',
            staleAnchorId: anchorNodeId,
            fallbackAnchorId: fallback,
            selected: selectedNodes.value.slice(),
          })
          anchorNodeId = fallback
          selectMindMapNode(ctx, fallback)
        }
      }
      const collapsedPaths = getMindMapCollapsedPaths(data.value)
      const collapsedNodeIds = getMindMapCollapsedNodeIds(
        data.value.nodes,
        data.value.connections,
        collapsedPaths
      )
      const inserted = insertMindMapSiblingInPlace(data.value.nodes, data.value.connections, {
        text,
        anchorNodeId,
        position,
        insertIndex: at?.insertIndex,
        afterNodeId: at?.afterNodeId,
        parentId: at?.parentId,
        nodeHeights: ctx.mindMapNodeHeights.value,
        nodeWidths: ctx.mindMapNodeWidths.value,
        diagramStyleId: data.value._mindmap_diagram_style as string | undefined,
        themeId: resolveActiveMindMapThemeId(data.value),
        nodeStyles: data.value._node_styles,
        collapsedNodeIds,
      })
      if (!inserted) return false
      const ok = commitMindMapSiblingInPlace(
        inserted,
        position === 'above' ? 'Add sibling above' : 'Add sibling'
      )
      if (ok) {
        recordMindMapSiblingInsertSuccess({
          newNodeId: inserted.newNodeId,
          anchorNodeId: nodeId,
          isTopLevel: inserted.isTopLevel,
        })
      } else {
        recordMindMapSiblingInsertFailure('commit_failed', {
          newNodeId: inserted.newNodeId,
          anchorNodeId: nodeId,
        })
      }
      return ok
    }

    if (nodeId === 'topic') return false

    const connections = data.value.connections
    const anchorNode = data.value.nodes.find((node) => node.id === nodeId)
    const topicNode = data.value.nodes.find((node) => node.id === 'topic')
    const anchorY = anchorNode?.position?.y
    const topicY = topicNode?.position?.y
    let anchorUid = readMindMapNodeUid(anchorNode)
    if (!anchorUid && anchorNode) {
      anchorUid = safeRandomUUID()
      anchorNode.data = {
        ...anchorNode.data,
        [MINDMAP_NODE_UID_DATA_KEY]: anchorUid,
      }
    }

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, nodeId, connections)
    if (!found) return false

    const insertIndex = position === 'above' ? found.indexInParent : found.indexInParent + 1
    const parentId = getMindMapParentId(connections, nodeId)
    const isTopLevel = parentId === 'topic'
    const newSibling = isTopLevel ? newTopLevelMindMapBranchSpec(text) : { text }
    const newSiblingUid = ensureMindMapBranchUid(newSibling)
    found.parentArray.splice(insertIndex, 0, newSibling)

    const beforeNodes = data.value.nodes
    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })
    let nodes = result.nodes
    let usedIncrementalL1Layout = false
    if (anchorUid != null) {
      if (isTopLevel && topicY != null && Number.isFinite(topicY)) {
        nodes = applyMindMapIncrementalTopLevelSiblingLayout(
          beforeNodes,
          result.nodes,
          result.connections,
          {
            anchorUid,
            newSiblingUid,
            insert: position,
            topicY,
            nodeHeights: ctx.mindMapNodeHeights.value,
            diagramStyleId:
              typeof ctx.data.value?._mindmap_diagram_style === 'string'
                ? ctx.data.value._mindmap_diagram_style
                : undefined,
          }
        )
        usedIncrementalL1Layout = true
      } else if (anchorY != null && Number.isFinite(anchorY)) {
        nodes = applyMindMapIncrementalSiblingYPreserve(result.nodes, {
          anchorUid,
          anchorY,
        })
      }
    }

    const newNodeId = findNodeIdByMindMapUid(nodes, newSiblingUid)
    const pathKey =
      newNodeId != null
        ? mindMapNodePathKey(newNodeId, result.connections)
        : computeSiblingPathKey(nodeId, insertIndex, connections)

    const committed = commitMindMapReloadWithSelect(
      ctx,
      { ...result, nodes },
      pathKey,
      position === 'above' ? 'Add sibling above' : 'Add sibling',
      usedIncrementalL1Layout ? { skipMindMapRecalc: true } : undefined
    )
    if (committed && newSiblingUid) {
      const liveNodes = data.value?.nodes ?? nodes
      const liveNewId = findNodeIdByMindMapUid(liveNodes, newSiblingUid)
      if (liveNewId) {
        selectMindMapNode(ctx, liveNewId)
      }
    }
    // Re-arm after commitMindMapReload cleared preserve; brief hold for first paint.
    if (committed && usedIncrementalL1Layout) {
      armMindMapPreserveIncomingYBriefly(ctx)
    }
    return committed
  }

  function insertMindMapSiblingsFromLines(
    anchorNodeId: string,
    lines: string[],
    options?: { topicSide?: 'left' | 'right' }
  ): number {
    if (isDiagramPresentationReadOnly(ctx)) return 0
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return 0
    if (!data.value?.nodes || !data.value?.connections) return 0

    const labels = lines.map((line) => line.trim()).filter(Boolean)
    if (labels.length === 0) return 0

    if (collabForeignLockBlocksAnyId(ctx, [anchorNodeId])) {
      emitCollabDeleteBlocked()
      return 0
    }

    // v2: shared in-place sibling helper (same path as Enter).
    if (readMindMapV2VisualDesignActive() && anchorNodeId !== 'topic') {
      let inserted = 0
      let cursorId = anchorNodeId
      for (const label of labels) {
        const ok = addMindMapSibling(cursorId, label, 'below')
        if (!ok) break
        const selected = selectedNodes.value[0]
        if (!selected) break
        cursorId = selected
        inserted += 1
      }
      return inserted
    }

    if (readMindMapV2VisualDesignActive() && anchorNodeId === 'topic') {
      // Topic paste: append top-level branches on the chosen side via branch add.
      const side = options?.topicSide ?? 'right'
      let inserted = 0
      for (const label of labels) {
        if (!addMindMapBranchOnSide(side, label)) break
        inserted += 1
      }
      return inserted
    }

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    let selectPathKey: string

    if (anchorNodeId === 'topic') {
      const side = options?.topicSide ?? 'right'
      const branches = side === 'left' ? spec.leftBranches : spec.rightBranches
      const startIndex = branches.length
      branches.push(...labels.map((text) => ({ text })))
      selectPathKey = `${side === 'left' ? 'l' : 'r'}/${startIndex + labels.length - 1}`
    } else {
      const found = findBranchByNodeId(
        spec.rightBranches,
        spec.leftBranches,
        anchorNodeId,
        connections
      )
      if (!found) return 0

      const insertIndex = found.indexInParent + 1
      found.parentArray.splice(insertIndex, 0, ...labels.map((text) => ({ text })))
      const pathKey = computeSiblingPathKey(
        anchorNodeId,
        insertIndex + labels.length - 1,
        connections
      )
      if (!pathKey) return 0
      selectPathKey = pathKey
    }

    const historyLabel = String(
      i18n.global.t('diagram.history.pasteSiblings', { count: labels.length })
    )
    const ok = applyMindMapSpecReload(
      spec.topic,
      spec.leftBranches,
      spec.rightBranches,
      historyLabel,
      selectPathKey
    )
    return ok ? labels.length : 0
  }

  function insertMindMapParentBranch(nodeId: string, text = defaultNewNodeText()): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (nodeId === 'topic') return false

    const connections = data.value.connections
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, connections)
    const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, nodeId, connections)
    if (!found) return false

    const pathKey = mindMapNodePathKey(nodeId, connections)
    if (!pathKey) return false

    const { branch, parentArray, indexInParent } = found
    parentArray.splice(indexInParent, 1, { text, children: [branch] })

    return applyMindMapSpecReload(
      spec.topic,
      spec.leftBranches,
      spec.rightBranches,
      'Insert parent branch',
      pathKey
    )
  }

  function performMindMapDirectionalAdd(
    nodeId: string,
    direction: 'top' | 'bottom' | 'left' | 'right'
  ): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (!readMindMapV2VisualDesignActive()) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false

    if (nodeId === 'topic') {
      if (direction === 'left') return addMindMapBranchOnSide('left')
      if (direction === 'right') return addMindMapBranchOnSide('right')
      return false
    }

    const isLeftBranch = nodeId.startsWith('branch-l-')
    const outward: 'left' | 'right' = isLeftBranch ? 'left' : 'right'
    const inward: 'left' | 'right' = isLeftBranch ? 'right' : 'left'

    if (direction === 'top') return addMindMapSibling(nodeId, defaultNewNodeText(), 'above')
    if (direction === 'bottom') return addMindMapSibling(nodeId, defaultNewNodeText(), 'below')
    if (direction === outward) return addMindMapChild(nodeId)
    if (direction === inward) return insertMindMapParentBranch(nodeId)
    return false
  }

  function expandMindMapPathToNode(nodeId: string): boolean {
    if (!readMindMapV2VisualDesignActive()) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (!nodeId || nodeId === 'topic') return false

    const connections = data.value.connections
    let paths = [...(data.value._collapsed_paths ?? [])]
    let changed = false

    const idsToExpand = new Set<string>([nodeId])
    let current: string | undefined = nodeId
    while (current && current !== 'topic') {
      const parent = connections.find((c) => c.target === current)?.source
      if (parent && mindMapNodeHasChildren(parent, connections)) {
        idsToExpand.add(parent)
      }
      current = parent
    }

    for (const id of idsToExpand) {
      const pathKey = mindMapNodePathKey(id, connections)
      if (!pathKey || !paths.includes(pathKey)) continue
      paths = paths.filter((p) => p !== pathKey)
      changed = true
    }

    if (!changed) return false
    setMindMapCollapsedPaths(data.value as Record<string, unknown>, paths)
    // Topology change: leave sticky L1-Enter preserve so Y can full-restack.
    ctx.mindMapPreserveIncomingY.value = false
    ctx.mindMapPreserveIncomingYNodeId.value = null
    ctx.scheduleMindMapRecalc()
    return true
  }

  function applyMindMapSubgraphPreview(result: SpecLoaderResult): void {
    if (!readMindMapV2VisualDesignActive()) return
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return
    commitMindMapReload(ctx, result)
    ctx.scheduleMindMapRecalc()
    emitCtxEvent(ctx, 'diagram:operation_completed', { operation: 'subgraph_preview' })
  }

  function restoreMindMapSubgraphSnapshot(snapshot: {
    nodes: DiagramNode[]
    connections: Connection[]
    nodeStyles?: Record<string, NodeStyle>
    collapsedPaths?: string[]
  }): void {
    if (!readMindMapV2VisualDesignActive()) return
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return
    if (!data.value) return
    data.value.nodes = snapshot.nodes
    data.value.connections = snapshot.connections
    data.value._node_styles = snapshot.nodeStyles
    setMindMapCollapsedPaths(data.value as Record<string, unknown>, snapshot.collapsedPaths ?? [])
    ctx.scheduleMindMapRecalc()
  }

  function clearMindMapSubgraphPreviewTags(): void {
    if (!readMindMapV2VisualDesignActive()) return
    if (!data.value?.nodes) return
    for (const node of data.value.nodes) {
      if (node.data && (node.data as Record<string, unknown>).subgraphPreview) {
        const next = { ...(node.data as Record<string, unknown>) }
        delete next.subgraphPreview
        node.data = next
      }
    }
  }

  function toggleMindMapCollapse(nodeId: string): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (!readMindMapV2VisualDesignActive()) return false
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false
    if (nodeId === 'topic') return false
    if (!mindMapNodeHasChildren(nodeId, data.value.connections)) return false

    const pathKey = mindMapNodePathKey(nodeId, data.value.connections)
    if (!pathKey) return false

    const current = data.value._collapsed_paths ?? []
    const collapsed = isMindMapPathCollapsed(nodeId, data.value.connections, current)
    const next = collapsed ? current.filter((p) => p !== pathKey) : [...current, pathKey]

    setMindMapCollapsedPaths(data.value as Record<string, unknown>, next)
    // Topology change: leave sticky L1-Enter preserve so Y can full-restack.
    ctx.mindMapPreserveIncomingY.value = false
    ctx.mindMapPreserveIncomingYNodeId.value = null
    ctx.scheduleMindMapRecalc()
    ctx.pushHistory(collapsed ? 'Expand branch' : 'Collapse branch')
    emitCtxEvent(ctx, 'diagram:operation_completed', {
      operation: collapsed ? 'expand_branch' : 'collapse_branch',
    })
    return true
  }

  function pasteMindMapClipboardBranches(
    anchorNodeId: string,
    branches: MindMapBranchSpec[],
    historyLabel?: string
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') {
      if (isMindMapSubgraphDebugEnabled()) {
        mindMapSubgraphDebugError('paste: wrong diagram type', { type: type.value })
      }
      return false
    }
    if (!data.value?.nodes || !data.value?.connections || branches.length === 0) {
      if (isMindMapSubgraphDebugEnabled()) {
        mindMapSubgraphDebugError('paste: missing data or empty branches', {
          hasNodes: Boolean(data.value?.nodes),
          hasConnections: Boolean(data.value?.connections),
          branchCount: branches.length,
        })
      }
      return false
    }

    const nodesBefore = data.value.nodes.length
    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    // Cut→paste keeps uids; copy→paste mints new ones when the source still exists.
    rebindMindMapBranchUidsForPaste(branches, collectMindMapNodeUids(data.value.nodes))
    if (isMindMapSubgraphDebugEnabled()) {
      mindMapSubgraphDebug('paste', 'spec snapshot before merge', {
        anchorNodeId,
        topic: spec.topic,
        branchPayload: branches.map((b) => b.text),
        lookup: debugMindMapSubgraphMergeLookup(
          data.value.nodes,
          data.value.connections,
          anchorNodeId
        ),
      })
    }

    const merged = mergeGeneratedBranchesIntoSpec(
      spec,
      anchorNodeId,
      branches,
      data.value.connections
    )
    if (!merged) {
      if (isMindMapSubgraphDebugEnabled()) {
        mindMapSubgraphDebugError('paste: mergeGeneratedBranchesIntoSpec returned null', {
          anchorNodeId,
          branches: branches.map((b) => b.text),
        })
      }
      return false
    }

    const label = historyLabel ?? String(i18n.global.t('diagram.history.pasteNodes'))
    const reloaded = applyMindMapSpecReload(
      merged.topic,
      merged.leftBranches,
      merged.rightBranches,
      label
    )
    if (isMindMapSubgraphDebugEnabled()) {
      const afterNodes = data.value?.nodes ?? []
      const _afterConnections = data.value?.connections ?? []
      mindMapSubgraphDebug('paste', 'applyMindMapSpecReload', {
        anchorNodeId,
        reloaded,
        nodesBefore,
        nodesAfter: afterNodes.length,
        branchIdsAfter: afterNodes
          .filter((n) => n.id.startsWith('branch-'))
          .map((n) => ({
            id: n.id,
            text: n.text,
          })),
      })
    }
    return reloaded
  }

  return {
    addMindMapBranch,
    addMindMapBranchOnSide,
    addMindMapChild,
    addMindMapSibling,
    insertMindMapSiblingsFromLines,
    insertMindMapParentBranch,
    performMindMapDirectionalAdd,
    removeMindMapNodes,
    getMindMapDescendantIds,
    moveMindMapBranch,
    getMindMapStructureMode,
    setMindMapStructureMode,
    toggleMindMapCollapse,
    expandMindMapPathToNode,
    applyMindMapSubgraphPreview,
    restoreMindMapSubgraphSnapshot,
    clearMindMapSubgraphPreviewTags,
    pasteMindMapClipboardBranches,
  }
}
