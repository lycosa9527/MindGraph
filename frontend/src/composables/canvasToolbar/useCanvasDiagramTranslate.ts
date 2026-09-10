/**
 * Full-diagram label translate: More Apps (live) and new-canvas preview (original kept).
 */
import { type ComputedRef, computed, inject } from 'vue'

import {
  applyThinkingCoinMutation,
  extractThinkingCoinsFooter,
} from '@/composables/auth/useThinkingCoinSync'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { useDiagramStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'
import { applyDiagramTranslationsToSpec } from '@/utils/applyDiagramTranslationsToSpec'
import { cloneDiagramSpecJson } from '@/utils/cloneDiagramSpecJson'
import {
  type DiagramTranslateItem,
  collectDiagramTranslateItems,
} from '@/utils/collectDiagramTranslateItems'
import { consumeDiagramTranslateNdjsonStream } from '@/utils/diagramTranslateStream'
import { canvasTranslateTargetForUiLocale } from '@/utils/translateLanguages'

function parseTranslateHttpDetail(payload: { detail?: unknown } | null): string | null {
  const detailRaw = payload?.detail
  if (typeof detailRaw === 'string') {
    return detailRaw
  }
  if (Array.isArray(detailRaw) && detailRaw.length > 0) {
    const first = detailRaw[0] as { msg?: string }
    if (typeof first.msg === 'string') {
      return first.msg
    }
  }
  return null
}

function asDiagramType(value: unknown): DiagramType | null {
  if (typeof value !== 'string') {
    return null
  }
  return VALID_DIAGRAM_TYPES.includes(value as DiagramType) ? (value as DiagramType) : null
}

export function useCanvasDiagramTranslate() {
  const diagramStore = useDiagramStore()
  const diagramTranslateUi = useDiagramTranslateUiStore()
  const llmResultsStore = useLLMResultsStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const uiStore = useUIStore()
  const authStore = useAuthStore()
  const { t } = useLanguage()
  const notify = useNotifications()

  const collabCanvas = inject<
    | {
        isDiagramOwner?: ComputedRef<boolean>
      }
    | undefined
  >('collabCanvas', undefined)

  const aiBlockedByCollab = computed(() => {
    if (!diagramStore.collabSessionActive) {
      return false
    }
    const own = collabCanvas?.isDiagramOwner
    if (!own) {
      return false
    }
    return !own.value
  })

  function warnIfUnavailable(): boolean {
    if (!authStore.isAuthenticated) {
      notify.warning(t('notification.signInToUse'))
      return true
    }
    if (!aiBlockedByCollab.value) {
      return false
    }
    notify.warning(t('canvas.toolbar.collabGuestFeatureBlocked'))
    return true
  }

  async function loadSpecView(
    spec: Record<string, unknown>,
    viewingTranslated: boolean
  ): Promise<boolean> {
    const diagramType = asDiagramType(diagramStore.type) ?? asDiagramType(spec.type)
    if (!diagramType) {
      notify.warning(t('canvas.toolbar.translateLabelFailed'))
      return false
    }
    diagramTranslateUi.setViewingTranslated(viewingTranslated)
    llmResultsStore.contentChangeIsFromModelSwitch = true
    const loaded = diagramStore.loadFromSpec(spec, diagramType, {
      preserveMindMapMeasures: true,
      preferLaidOutMindMapNodes: true,
    })
    if (!loaded) {
      llmResultsStore.contentChangeIsFromModelSwitch = false
      notify.warning(t('canvas.toolbar.translateLabelFailed'))
      diagramTranslateUi.setViewingTranslated(false)
      return false
    }
    return true
  }

  async function showTranslatedSpec(spec: Record<string, unknown>): Promise<boolean> {
    return loadSpecView(spec, true)
  }

  function settlePreviewPhase(): void {
    if (diagramTranslateUi.translatedSpec) {
      diagramTranslateUi.setPhase('ready')
      return
    }
    diagramTranslateUi.setPhase('idle')
  }

  async function leaveTranslatePreview(): Promise<void> {
    const original = diagramTranslateUi.pendingSourceSpec
    if (!original) {
      diagramTranslateUi.setViewingTranslated(false)
      settlePreviewPhase()
      return
    }
    diagramTranslateUi.invalidateInFlight()
    settlePreviewPhase()
    if (!diagramTranslateUi.viewingTranslated) {
      return
    }
    await loadSpecView(original, false)
  }

  async function runDiagramTranslate(
    items: DiagramTranslateItem[],
    options?: {
      targetUiLocale?: string
      deferCanvasApply?: boolean
      sourceSpec?: Record<string, unknown> | null
    }
  ): Promise<void> {
    if (diagramTranslateUi.inFlight) {
      return
    }
    const uiCode = options?.targetUiLocale ?? uiStore.language
    const targetLanguage = canvasTranslateTargetForUiLocale(uiCode)
    if (targetLanguage === 'en' && uiCode !== 'en') {
      notify.info(t('canvas.toolbar.translateLabelFallbackEnInfo'))
    }
    const deferCanvasApply = options?.deferCanvasApply === true
    const sourceSpec = options?.sourceSpec ?? null
    diagramTranslateUi.setInFlight(true)
    if (deferCanvasApply) {
      diagramTranslateUi.setPhase('sending')
    } else {
      diagramTranslateUi.openBanner()
    }
    const signal = diagramTranslateUi.beginStream()
    const generation = diagramTranslateUi.streamGeneration
    const deferredPatches: Array<{ itemId: string; kind: 'node' | 'connection'; text: string }> = []
    let streamFinishedOk = false
    try {
      const body: Record<string, unknown> = {
        items: items.map((item) => ({
          item_id: item.itemId,
          text: item.text.trim(),
          item_kind: item.kind,
        })),
        target_language: targetLanguage,
        diagram_type: diagramStore.type ?? undefined,
        ui_locale: uiCode,
      }
      const activeId = savedDiagramsStore.activeDiagramId
      if (activeId) {
        body.diagram_id = activeId
      }
      const response = await authFetch('/api/canvas/translate_diagram_labels_stream', {
        method: 'POST',
        signal,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/x-ndjson',
        },
        body: JSON.stringify(body),
      })
      if (!diagramTranslateUi.isCurrentGeneration(generation)) {
        return
      }
      if (!response.ok) {
        if (signal.aborted) {
          return
        }
        const errorPayload = (await response.json().catch(() => null)) as {
          detail?: unknown
        } | null
        notify.warning(
          parseTranslateHttpDetail(errorPayload) || t('canvas.toolbar.translateLabelFailed')
        )
        if (deferCanvasApply) {
          diagramTranslateUi.setPhase('error')
        }
        return
      }
      if (deferCanvasApply) {
        diagramTranslateUi.setPhase('waiting')
      }
      await consumeDiagramTranslateNdjsonStream(response, {
        onStart(totalItems: number) {
          if (signal.aborted || !diagramTranslateUi.isCurrentGeneration(generation)) {
            return
          }
          diagramTranslateUi.setTotal(totalItems)
        },
        onItem(row) {
          if (signal.aborted || !diagramTranslateUi.isCurrentGeneration(generation)) {
            return
          }
          const text = row.translated_text.trim()
          if (!text) {
            return
          }
          if (deferCanvasApply) {
            diagramTranslateUi.setPhase('streaming')
            deferredPatches.push({ itemId: row.item_id, kind: row.item_kind, text })
          } else if (row.item_kind === 'connection') {
            diagramStore.updateConnectionLabel(row.item_id, text)
          } else {
            eventBus.emit('node:text_updated', { nodeId: row.item_id, text })
          }
          diagramTranslateUi.bumpApplied()
        },
        onDone(donePayload) {
          if (!diagramTranslateUi.isCurrentGeneration(generation)) {
            return
          }
          streamFinishedOk = true
          applyThinkingCoinMutation(extractThinkingCoinsFooter(donePayload))
        },
        onError(message) {
          if (signal.aborted || !diagramTranslateUi.isCurrentGeneration(generation)) {
            return
          }
          notify.warning(message || t('canvas.toolbar.translateLabelFailed'))
          if (deferCanvasApply) {
            diagramTranslateUi.setPhase('error')
          }
        },
      })
      if (!diagramTranslateUi.isCurrentGeneration(generation)) {
        return
      }
      if (streamFinishedOk) {
        await ensureFontsForLanguageCode(targetLanguage)
        if (deferCanvasApply && sourceSpec) {
          const translated = applyDiagramTranslationsToSpec(sourceSpec, deferredPatches)
          diagramTranslateUi.setTranslatedSpec(translated)
          await showTranslatedSpec(translated)
          diagramTranslateUi.setPhase('ready')
        }
        notify.success(t('canvas.toolbar.translateLabelDone'))
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return
      }
      if (!diagramTranslateUi.isCurrentGeneration(generation)) {
        return
      }
      console.error('Translate diagram failed:', error)
      notify.warning(t('canvas.toolbar.translateLabelFailed'))
      if (deferCanvasApply) {
        diagramTranslateUi.setPhase('error')
      }
    } finally {
      if (diagramTranslateUi.isCurrentGeneration(generation)) {
        if (!deferCanvasApply) {
          diagramTranslateUi.closeBanner()
        }
        diagramTranslateUi.setInFlight(false)
      }
    }
  }

  function runFromCurrentDiagram(): void {
    if (warnIfUnavailable()) {
      return
    }
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    const items = collectDiagramTranslateItems(diagramStore.data)
    if (items.length === 0) {
      notify.warning(t('canvas.toolbar.translateLabelDiagramEmpty'))
      return
    }
    void runDiagramTranslate(items)
  }

  function snapshotCurrentSpec(): Record<string, unknown> | null {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return null
    }
    const spec = diagramStore.getSpecForSave()
    if (!spec) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return null
    }
    const items = collectDiagramTranslateItems(spec)
    if (items.length === 0) {
      notify.warning(t('canvas.toolbar.translateLabelDiagramEmpty'))
      return null
    }
    return cloneDiagramSpecJson(spec)
  }

  function startPendingTranslate(): void {
    if (warnIfUnavailable()) {
      return
    }
    const target = diagramTranslateUi.pendingTargetLanguage
    const spec = diagramTranslateUi.pendingSourceSpec
    if (!target || !spec) {
      return
    }
    const items = collectDiagramTranslateItems(spec)
    if (items.length === 0) {
      notify.warning(t('canvas.toolbar.translateLabelDiagramEmpty'))
      return
    }
    void runDiagramTranslate(items, {
      targetUiLocale: target,
      deferCanvasApply: true,
      sourceSpec: spec,
    })
  }

  function armAndStartTranslate(targetLocale: string): boolean {
    if (warnIfUnavailable()) {
      return false
    }
    const spec = diagramTranslateUi.viewingTranslated
      ? diagramTranslateUi.pendingSourceSpec
      : snapshotCurrentSpec()
    if (!spec) {
      return false
    }
    const cached = diagramTranslateUi.translatedSpec
    if (
      diagramTranslateUi.pendingTargetLanguage === targetLocale &&
      cached &&
      !diagramTranslateUi.inFlight
    ) {
      if (!diagramTranslateUi.viewingTranslated) {
        void showTranslatedSpec(cached)
      }
      return true
    }
    diagramTranslateUi.invalidateInFlight()
    diagramTranslateUi.armPending(targetLocale, spec)
    startPendingTranslate()
    return true
  }

  return {
    aiBlockedByCollab,
    armAndStartTranslate,
    leaveTranslatePreview,
    runFromCurrentDiagram,
  }
}
