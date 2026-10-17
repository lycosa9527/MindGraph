/**
 * Set / clear path-keyed mind-map node adornments.
 */
import { i18n } from '@/i18n'
import type { MindMapNodeAdornment } from '@/types'
import {
  mergeNodeAdornment,
  mindMapAdornmentDeletePatch,
  mindMapAdornmentPathKey,
  mindMapAdornmentStorageKeys,
  mindMapNodeHasAdornment,
  readMindMapAdornments,
  readNodeAdornment,
  remapMindMapAdornmentsAfterReload,
  sanitizeMindMapHref,
  sanitizeMindMapImageUrl,
  writeMindMapAdornments,
} from '@/utils/mindMapAdornments'
import { isMindMapSummaryNodeId } from '@/utils/mindMapSummary'

import { remapMindMapNodeIdAfterReload } from './mindMapCollapse'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import type { DiagramContext } from './types'

export function setMindMapNodeAdornment(
  ctx: DiagramContext,
  nodeId: string,
  patch: MindMapNodeAdornment,
  historyLabel: string
): boolean {
  if (isDiagramPresentationReadOnly(ctx)) return false
  const data = ctx.data.value
  if (!data) return false
  const isMindMap = ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map'
  if (isMindMap && !data.connections) return false
  if (isMindMapSummaryNodeId(nodeId)) return false
  const path = isMindMap ? mindMapAdornmentPathKey(nodeId, data.connections ?? []) : nodeId
  if (!path) return false

  const all = readMindMapAdornments(data)
  const merged = mergeNodeAdornment(all[path], patch)
  ctx.pushHistory(historyLabel)
  if (merged) all[path] = merged
  else delete all[path]
  writeMindMapAdornments(data, all)
  if (isMindMap) ctx.scheduleMindMapRecalc()
  return true
}

export function setMindMapNodeIcon(ctx: DiagramContext, nodeId: string, icon: string): boolean {
  return setMindMapNodeAdornment(
    ctx,
    nodeId,
    { icon },
    String(i18n.global.t('canvas.ribbon.insertIcon'))
  )
}

export function setMindMapNodeHref(ctx: DiagramContext, nodeId: string, rawHref: string): boolean {
  const href = sanitizeMindMapHref(rawHref)
  if (href == null && rawHref.trim()) return false
  return setMindMapNodeAdornment(
    ctx,
    nodeId,
    { href: href ?? '' },
    String(i18n.global.t('canvas.ribbon.insertLink'))
  )
}

export function setMindMapNodeImage(ctx: DiagramContext, nodeId: string, rawUrl: string): boolean {
  const imageUrl = sanitizeMindMapImageUrl(rawUrl)
  if (imageUrl == null && rawUrl.trim()) return false
  return setMindMapNodeAdornment(
    ctx,
    nodeId,
    { imageUrl: imageUrl ?? '' },
    String(i18n.global.t('canvas.ribbon.insertImage'))
  )
}

/** Strip the top adornment layer on each node (link → image → icon); one undo step total. */
export function clearMindMapNodeAdornments(
  ctx: DiagramContext,
  nodeIds: readonly string[]
): number {
  if (isDiagramPresentationReadOnly(ctx)) return 0
  const data = ctx.data.value
  if (!data?.connections) return 0
  const isMindMap = ctx.type.value === 'mindmap' || ctx.type.value === 'mind_map'
  if (!isMindMap) return 0

  const all = readMindMapAdornments(data)
  let cleared = 0
  let touched = false
  let historyLabel = 'Remove adornment'

  for (const nodeId of nodeIds) {
    if (isMindMapSummaryNodeId(nodeId)) continue
    const current = readNodeAdornment(data, nodeId, data.connections)
    if (!current || !mindMapNodeHasAdornment(current)) continue
    const patch = mindMapAdornmentDeletePatch(current)
    if (!patch) continue

    if (!touched) {
      if (patch.href === '') historyLabel = 'Remove link'
      else if (patch.imageUrl === '') historyLabel = 'Remove image'
      else if (patch.icon === '') historyLabel = 'Remove icon'
    }

    for (const key of mindMapAdornmentStorageKeys(nodeId, data.connections)) {
      const stored = all[key]
      if (!stored || !mindMapNodeHasAdornment(stored)) continue
      const merged = mergeNodeAdornment(stored, patch)
      if (merged) all[key] = merged
      else delete all[key]
      touched = true
    }
    cleared += 1
  }

  if (!touched) return 0

  ctx.pushHistory(historyLabel)
  writeMindMapAdornments(data, all)
  ctx.scheduleMindMapRecalc()
  return cleared
}

export function remapAdornmentsAfterTreeReload(
  ctx: DiagramContext,
  oldNodes: Parameters<typeof remapMindMapAdornmentsAfterReload>[1],
  oldConnections: Parameters<typeof remapMindMapAdornmentsAfterReload>[2],
  newNodes: Parameters<typeof remapMindMapAdornmentsAfterReload>[3],
  newConnections: Parameters<typeof remapMindMapAdornmentsAfterReload>[4]
): void {
  const data = ctx.data.value
  if (!data) return
  const remapped = remapMindMapAdornmentsAfterReload(
    readMindMapAdornments(data),
    oldNodes,
    oldConnections,
    newNodes,
    newConnections,
    remapMindMapNodeIdAfterReload
  )
  writeMindMapAdornments(data, remapped)
}
