/**
 * Applies Kitty pedagogical-review WebSocket payloads: highlight nodes + summary toast.
 */
import { nextTick, onMounted, onUnmounted } from 'vue'

import { useDiagramStore } from '@/stores'

import { eventBus } from '../core/useEventBus'
import { useNotifications } from '../core/useNotifications'

export interface KittyDiagramReviewAnnotationItemPayload {
  node_id: string
  reason: string
  suggestion?: string
}

function buildDetailLines(rows: KittyDiagramReviewAnnotationItemPayload[]): string {
  const lines: string[] = []
  const seen = new Set<string>()
  for (const it of rows) {
    const nid = it.node_id.trim()
    const reason = it.reason.trim()
    if (!reason) continue
    const sug = typeof it.suggestion === 'string' ? it.suggestion.trim() : ''
    const body = sug ? `${reason}\n→ ${sug}` : reason
    const line = nid ? `${nid}: ${body}` : body
    if (seen.has(line)) continue
    seen.add(line)
    lines.push(line)
  }
  return lines.join('\n\n')
}

export function useKittyDiagramReviewAnnotationBus(ownerId: string): void {
  const diagramStore = useDiagramStore()
  const notifications = useNotifications()

  let unsub: (() => void) | undefined

  onMounted(() => {
    unsub = eventBus.onWithOwner(
      'kitty:diagram_review_annotation',
      (payload: { summary?: string; items?: KittyDiagramReviewAnnotationItemPayload[] }) => {
        const rawItems = Array.isArray(payload.items) ? payload.items : []
        const normalized: KittyDiagramReviewAnnotationItemPayload[] = rawItems.map((row) => ({
          node_id: typeof row.node_id === 'string' ? row.node_id : '',
          reason: typeof row.reason === 'string' ? row.reason : String(row.reason ?? ''),
          suggestion: typeof row.suggestion === 'string' ? row.suggestion : undefined,
        }))

        const map: Record<string, { reason: string; suggestion?: string }> = {}
        const ids: string[] = []
        for (const it of normalized) {
          const nid = it.node_id.trim()
          if (!nid) continue
          const reason = it.reason.trim()
          if (!reason) continue
          map[nid] = {
            reason,
            ...(typeof it.suggestion === 'string' && it.suggestion.trim()
              ? { suggestion: it.suggestion.trim() }
              : {}),
          }
          ids.push(nid)
        }

        diagramStore.applyKittyDiagramReviewAnnotations(map)

        const summaryRaw = typeof payload.summary === 'string' ? payload.summary.trim() : ''
        if (!summaryRaw && !Object.keys(map).length) return

        if (ids.length) {
          diagramStore.selectNodes(ids)
          void nextTick(() => eventBus.emit('view:fit_diagram_requested', {}))
        }

        const detailBody = buildDetailLines(normalized)
        if (!summaryRaw && !detailBody) return

        notifications.showNotification({
          title: summaryRaw || 'Kitty diagram review',
          message: summaryRaw ? detailBody || summaryRaw : detailBody,
          type: 'warning',
          duration: 10_000,
        })
      },
      ownerId
    )
  })

  onUnmounted(() => {
    unsub?.()
    unsub = undefined
  })
}
