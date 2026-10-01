/**
 * Set / clear path-keyed mind-map node adornments.
 */
import { i18n } from '@/i18n'
import type { MindMapNodeAdornment } from '@/types'
import {
  mergeNodeAdornment,
  mindMapAdornmentPathKey,
  readMindMapAdornments,
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
  if (!data?.connections) return false
  if (isMindMapSummaryNodeId(nodeId)) return false
  const path = mindMapAdornmentPathKey(nodeId, data.connections)
  if (!path) return false

  const all = readMindMapAdornments(data)
  const merged = mergeNodeAdornment(all[path], patch)
  ctx.pushHistory(historyLabel)
  if (merged) all[path] = merged
  else delete all[path]
  writeMindMapAdornments(data, all)
  ctx.scheduleMindMapRecalc()
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
