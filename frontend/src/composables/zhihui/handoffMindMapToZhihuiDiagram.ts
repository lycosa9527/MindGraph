/**
 * Canvas → 智绘「图示生图」handoff.
 * Persists the live mind map, then opens ZhiHui on the matching conversation
 * (if any) or a blank create surface with that diagram selected.
 *
 * Safe to call from event handlers — uses the i18n singleton / Pinia, not
 * ``useI18n`` / ``useLanguage`` (those require Vue setup context).
 */
import type { Router } from 'vue-router'

import type { SaveFlushResult } from '@/composables/editor/useDiagramAutoSave'
import { useDiagramSpecForPersist } from '@/composables/editor/useDiagramSpecForSave'
import { notify } from '@/composables/core/notifications'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'
import { useZhihuiHistoryStore } from '@/stores/zhihuiHistory'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'

export type HandoffMindMapToZhihuiOptions = {
  router: Router
  /** Prefer canvas autosave flush so dirty edits land before ZhiHui loads. */
  flush: () => Promise<SaveFlushResult>
  language: string
}

function isMindMapType(type: string | null | undefined): boolean {
  const normalized = (type || '').toLowerCase().replace('-', '_')
  return normalized === 'mindmap' || normalized === 'mind_map'
}

function tt(key: string, named?: Record<string, unknown>): string {
  if (named) {
    return String(i18n.global.t(key, named))
  }
  return String(i18n.global.t(key))
}

/**
 * Save (if needed) and navigate to ZhiHui.
 * Prefer an existing 图示生图 conversation for the diagram; otherwise land with
 * ``diagramId`` selected on a blank create surface.
 */
export async function handoffMindMapToZhihuiDiagram(
  options: HandoffMindMapToZhihuiOptions
): Promise<boolean> {
  const { router, flush, language } = options
  const authStore = useAuthStore()
  const featureFlags = useFeatureFlagsStore()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const historyStore = useZhihuiHistoryStore()
  const uiStore = useUIStore()
  const getDiagramSpecForPersist = useDiagramSpecForPersist()

  if (!authStore.isAuthenticated) {
    notify.warning(tt('editor.saveFailed'))
    return false
  }
  if (!featureFlags.getFeatureZhihui() || !authStore.canAccessZhihui) {
    notify.warning(tt('canvas.topBar.zhihuiUnavailable'))
    return false
  }
  if (!isMindMapType(diagramStore.type)) {
    notify.warning(tt('canvas.topBar.zhihuiNeedMindmap'))
    return false
  }

  const flushResult = await flush()
  if (flushResult.reason === 'error') {
    notify.error(tt('canvas.topBar.zhihuiSaveFailed'))
    return false
  }

  let diagramId = savedDiagramsStore.activeDiagramId

  if (!diagramId && flushResult.reason === 'skipped_slots_full') {
    notify.warning(tt('auth.diagramLimitReached', { max: savedDiagramsStore.maxDiagrams }))
    return false
  }

  if (!diagramId) {
    const title = resolveDiagramTitleForSave(
      diagramStore.effectiveTitle,
      diagramStore.type,
      uiStore.language
    )
    const spec = getDiagramSpecForPersist()
    if (!spec) {
      notify.warning(tt('canvas.export.noDiagramData'))
      return false
    }
    const saveResult = await savedDiagramsStore.autoSaveDiagram(
      title,
      diagramStore.type || 'mindmap',
      spec,
      language,
      null,
      diagramStore.sessionEditCount
    )
    if (!saveResult.success || !saveResult.diagramId) {
      if (saveResult.error === 'No available slots') {
        notify.warning(tt('auth.diagramLimitReached', { max: savedDiagramsStore.maxDiagrams }))
      } else {
        notify.error(tt('canvas.topBar.zhihuiSaveFailed'))
      }
      return false
    }
    diagramId = saveResult.diagramId
  }

  const title = resolveDiagramTitleForSave(
    diagramStore.effectiveTitle,
    diagramStore.type,
    uiStore.language
  )

  // Keep library list fresh so ZhiHui dropdown can resolve the saved row.
  void savedDiagramsStore.fetchDiagrams(1, 50, { force: true })

  const existing = await historyStore.findLatestConversationForDiagram(diagramId)
  if (existing?.id) {
    // Do not startLanding — preserve selection; page hydrates from conversationId.
    historyStore.selectItem(existing.id)
    await router.push({
      name: 'ZhiHui',
      query: {
        conversationId: existing.id,
        diagramId,
        ...(title.trim() ? { diagramTitle: title.trim() } : {}),
      },
    })
    return true
  }

  historyStore.startLanding('diagram')
  await router.push({
    name: 'ZhiHui',
    query: {
      mode: 'diagram',
      diagramId,
      ...(title.trim() ? { diagramTitle: title.trim() } : {}),
    },
  })
  return true
}
