import { type ComputedRef, computed, inject, ref } from 'vue'

import {
  Camera,
  Keyboard,
  Languages,
  Layers,
  LayoutGrid,
  type LucideIcon,
  Package,
} from '@lucide/vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useAutoComplete } from '@/composables/editor/useAutoComplete'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { useDiagramStore } from '@/stores'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'
import { authFetch } from '@/utils/api'
import { consumeDiagramTranslateNdjsonStream } from '@/utils/diagramTranslateStream'
import { canvasTranslateTargetForUiLocale } from '@/utils/translateLanguages'

import {
  canvasVirtualKeyboardOpen,
  ensureCanvasVirtualKeyboardUiVersionSync,
  toggleCanvasVirtualKeyboard,
} from './useCanvasVirtualKeyboardOpen'

export type MoreAppHandlerKey = 'concept_map_modes'

export type MoreAppItem = {
  name: string
  icon: LucideIcon
  desc: string
  tag?: string
  iconBg: string
  iconColor: string
  handlerKey?: MoreAppHandlerKey
  appKey?: 'waterfall' | 'learning_sheet' | 'snapshot' | 'virtual_keyboard' | 'translate_diagram'
}

export function useCanvasToolbarApps() {
  ensureCanvasVirtualKeyboardUiVersionSync()
  const diagramStore = useDiagramStore()
  const diagramTranslateUi = useDiagramTranslateUiStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const uiStore = useUIStore()
  const { t } = useLanguage()
  const notify = useNotifications()
  const { isGenerating: isAIGenerating, autoComplete, validateForAutoComplete } = useAutoComplete()

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

  const diagramTranslateInFlight = ref(false)

  const isConceptMap = computed(() => diagramStore.type === 'concept_map')

  const moreApps = computed((): MoreAppItem[] => {
    const conceptMapModesRow: MoreAppItem = {
      name: t('canvas.toolbar.moreAppConceptMapModes'),
      icon: Layers,
      desc: t('canvas.toolbar.moreAppConceptMapModesDesc'),
      tag: t('canvas.toolbar.tagSoon'),
      iconBg: 'bg-emerald-100',
      iconColor: 'text-emerald-600',
      handlerKey: 'concept_map_modes',
    }
    const apps: MoreAppItem[] = [
      {
        appKey: 'waterfall',
        name: t('canvas.toolbar.moreAppWaterfall'),
        icon: LayoutGrid,
        desc: t('canvas.toolbar.moreAppWaterfallDesc'),
        tag: t('canvas.toolbar.tagHot'),
        iconBg: 'bg-blue-100',
        iconColor: 'text-blue-600',
      },
      {
        appKey: 'learning_sheet',
        name: t('canvas.toolbar.moreAppLearningSheet'),
        icon: Package,
        desc: t('canvas.toolbar.moreAppLearningSheetDesc'),
        iconBg: 'bg-purple-100',
        iconColor: 'text-purple-600',
      },
      {
        appKey: 'snapshot',
        name: t('canvas.toolbar.moreAppSnapshot'),
        icon: Camera,
        desc: t('canvas.toolbar.moreAppSnapshotDesc'),
        iconBg: 'bg-amber-100',
        iconColor: 'text-amber-600',
      },
      {
        appKey: 'translate_diagram',
        name: t('canvas.toolbar.moreAppTranslateLabel'),
        icon: Languages,
        desc: t('canvas.toolbar.moreAppTranslateLabelDesc'),
        iconBg: 'bg-teal-100',
        iconColor: 'text-teal-600',
      },
      ...(uiStore.uiVersion === 'international'
        ? [
            {
              appKey: 'virtual_keyboard' as const,
              name: t('canvas.toolbar.moreAppVirtualKeyboard'),
              icon: Keyboard,
              desc: t('canvas.toolbar.moreAppVirtualKeyboardDesc'),
              iconBg: 'bg-slate-100',
              iconColor: 'text-slate-600',
            },
          ]
        : []),
    ]
    const withoutWaterfall = isConceptMap.value
      ? apps.filter((a) => a.appKey !== 'waterfall')
      : apps
    let list: MoreAppItem[]
    if (isConceptMap.value) {
      list = [conceptMapModesRow, ...withoutWaterfall]
    } else {
      list = withoutWaterfall
    }
    if (aiBlockedByCollab.value) {
      return list.filter(
        (a) =>
          a.appKey !== 'learning_sheet' &&
          a.appKey !== 'snapshot' &&
          a.appKey !== 'translate_diagram'
      )
    }
    return list
  })

  async function handleAIGenerate() {
    if (diagramStore.collabSessionActive) {
      notify.warning(t('canvas.toolbar.collabLiveAiDisabled'))
      return
    }
    const validation = validateForAutoComplete()
    if (!validation.valid) {
      notify.warning(validation.error || t('canvas.toolbar.cannotGenerate'))
      return
    }

    const result = await autoComplete({
      promptSuffix: diagramStore.isLearningSheet ? ' 半成品' : undefined,
    })
    if (!result.success && result.error) {
      console.error('Auto-complete failed:', result.error)
    }
  }

  function handleConceptGeneration() {
    if (!diagramStore.data?.nodes?.length) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }
    const options: Record<string, unknown> = {}
    if (isConceptMap.value) {
      options.useConceptListHeader = true
    }
    if (isConceptMap.value && diagramStore.selectedNodes.length === 1) {
      const nodeId = diagramStore.selectedNodes[0]
      const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
      const topicNode = diagramStore.data?.nodes?.find(
        (n) => n.type === 'topic' || n.type === 'center' || n.id === 'root'
      )
      if (node && node.id !== topicNode?.id && node.text?.trim()) {
        options.conceptMapNodeId = node.id
        options.conceptMapNodeText = (node.text ?? '').trim()
      }
    }
    eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'toolbar', options })
  }

  function handleMoreAppItem(app: MoreAppItem) {
    if (app.handlerKey === 'concept_map_modes') {
      notify.info(t('canvas.toolbar.conceptMapModesDev'))
      return
    }
    void handleMoreApp(app)
  }

  function collectDiagramTranslateItems(): Array<{
    itemId: string
    text: string
    kind: 'node' | 'connection'
  }> {
    const out: Array<{ itemId: string; text: string; kind: 'node' | 'connection' }> = []
    for (const node of diagramStore.data?.nodes ?? []) {
      const text = String(
        node?.text ?? (node?.data as { label?: string } | undefined)?.label ?? ''
      ).trim()
      if (text) {
        out.push({ itemId: node.id, text, kind: 'node' })
      }
    }
    for (const conn of diagramStore.data?.connections ?? []) {
      const text = String(conn.label ?? '').trim()
      if (text) {
        out.push({ itemId: conn.id, text, kind: 'connection' })
      }
    }
    return out
  }

  async function runToolbarDiagramTranslate(
    items: Array<{ itemId: string; text: string; kind: 'node' | 'connection' }>
  ): Promise<void> {
    if (diagramTranslateInFlight.value) {
      return
    }
    const uiCode = uiStore.language
    const targetLanguage = canvasTranslateTargetForUiLocale(uiCode)
    if (targetLanguage === 'en' && uiCode !== 'en') {
      notify.info(t('canvas.toolbar.translateLabelFallbackEnInfo'))
    }
    diagramTranslateInFlight.value = true
    diagramTranslateUi.openBanner()
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
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/x-ndjson',
        },
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as {
          detail?: unknown
        } | null
        let detail: string | null = null
        const detailRaw = errorPayload?.detail
        if (typeof detailRaw === 'string') {
          detail = detailRaw
        } else if (Array.isArray(detailRaw) && detailRaw.length > 0) {
          const first = detailRaw[0] as { msg?: string }
          if (typeof first.msg === 'string') {
            detail = first.msg
          }
        }
        notify.warning(detail || t('canvas.toolbar.translateLabelFailed'))
        return
      }
      await consumeDiagramTranslateNdjsonStream(response, {
        onStart(totalItems: number) {
          diagramTranslateUi.setTotal(totalItems)
        },
        onItem(row) {
          const text = row.translated_text.trim()
          if (!text) {
            return
          }
          if (row.item_kind === 'connection') {
            diagramStore.updateConnectionLabel(row.item_id, text)
          } else {
            eventBus.emit('node:text_updated', { nodeId: row.item_id, text })
          }
          diagramTranslateUi.bumpApplied()
        },
        onDone() {
          streamFinishedOk = true
        },
        onError(message) {
          notify.warning(message || t('canvas.toolbar.translateLabelFailed'))
        },
      })
      if (streamFinishedOk) {
        await ensureFontsForLanguageCode(targetLanguage)
        notify.success(t('canvas.toolbar.translateLabelDone'))
      }
    } catch (error) {
      console.error('Translate diagram failed:', error)
      notify.warning(t('canvas.toolbar.translateLabelFailed'))
    } finally {
      diagramTranslateUi.closeBanner()
      diagramTranslateInFlight.value = false
    }
  }

  async function handleMoreApp(app: MoreAppItem) {
    if (
      aiBlockedByCollab.value &&
      (app.appKey === 'learning_sheet' ||
        app.appKey === 'snapshot' ||
        app.appKey === 'translate_diagram')
    ) {
      notify.warning(t('canvas.toolbar.collabGuestFeatureBlocked'))
      return
    }
    if (app.appKey === 'waterfall') {
      if (!diagramStore.data?.nodes?.length) {
        notify.warning(t('canvas.toolbar.createDiagramFirst'))
        return
      }
      eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'toolbar' })
      return
    }
    if (app.appKey === 'learning_sheet') {
      if (!diagramStore.data?.nodes?.length) {
        notify.warning(t('canvas.toolbar.createDiagramFirst'))
        return
      }
      if (diagramStore.isLearningSheet) {
        diagramStore.restoreFromLearningSheetMode()
        notify.success(t('canvas.toolbar.switchedToRegular'))
      } else if (diagramStore.hasPreservedLearningSheet()) {
        diagramStore.applyLearningSheetView()
        notify.success(t('canvas.toolbar.learningSheetRestored'))
      } else {
        const spec = diagramStore.getSpecForSave()
        if (spec && diagramStore.type) {
          diagramStore.loadFromSpec(
            {
              ...spec,
              is_learning_sheet: true,
              hidden_node_percentage: 0.2,
            },
            diagramStore.type
          )
          notify.success(t('canvas.toolbar.switchedLearningSheetMode'))
        }
      }
      return
    }
    if (app.appKey === 'snapshot') {
      if (!diagramStore.data?.nodes?.length) {
        notify.warning(t('canvas.toolbar.createDiagramFirst'))
        return
      }
      if (!savedDiagramsStore.activeDiagramId) {
        notify.warning(t('canvas.toolbar.snapshotSaveFirst'))
        return
      }
      eventBus.emit('snapshot:requested', {})
      return
    }
    if (app.appKey === 'virtual_keyboard') {
      toggleCanvasVirtualKeyboard()
      return
    }
    if (app.appKey === 'translate_diagram') {
      if (!diagramStore.data?.nodes?.length) {
        notify.warning(t('canvas.toolbar.createDiagramFirst'))
        return
      }
      const items = collectDiagramTranslateItems()
      if (items.length === 0) {
        notify.warning(t('canvas.toolbar.translateLabelDiagramEmpty'))
        return
      }
      void runToolbarDiagramTranslate(items)
      return
    }
    notify.info(t('canvas.toolbar.featureInDevelopment', { name: app.name }))
  }

  return {
    aiBlockedByCollab,
    isAIGenerating,
    isConceptMap,
    moreApps,
    virtualKeyboardOpen: canvasVirtualKeyboardOpen,
    handleAIGenerate,
    handleConceptGeneration,
    handleMoreAppItem,
  }
}
