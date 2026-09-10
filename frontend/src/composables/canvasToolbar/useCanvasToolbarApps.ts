import { type ComputedRef, computed, inject } from 'vue'

import {
  Camera,
  Keyboard,
  Languages,
  Layers,
  LayoutGrid,
  type LucideIcon,
  Package,
} from '@lucide/vue'

import { useCanvasDiagramTranslate } from '@/composables/canvasToolbar/useCanvasDiagramTranslate'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useAutoComplete } from '@/composables/editor/useAutoComplete'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import {
  buildEducationStageInstructions,
  isEducationStage,
  mergeGenerationInstructions,
} from '@/constants/educationStage'
import { useDiagramStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'
import { claimThinkingCoinEvent } from '@/utils/claimThinkingCoinEvent'

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
  const savedDiagramsStore = useSavedDiagramsStore()
  const { runFromCurrentDiagram } = useCanvasDiagramTranslate()
  const uiStore = useUIStore()
  const authStore = useAuthStore()
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

  const isConceptMap = computed(() => diagramStore.type === 'concept_map')
  const useMindMapV2 = useMindMapV2Chrome()

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
      {
        appKey: 'virtual_keyboard' as const,
        name: t('canvas.toolbar.moreAppVirtualKeyboard'),
        icon: Keyboard,
        desc: t('canvas.toolbar.moreAppVirtualKeyboardDesc'),
        iconBg: 'bg-slate-100',
        iconColor: 'text-slate-600',
      },
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
      list = list.filter(
        (a) =>
          a.appKey !== 'learning_sheet' &&
          a.appKey !== 'snapshot' &&
          a.appKey !== 'translate_diagram'
      )
    }
    if (useMindMapV2.value) {
      return list.filter((a) => a.appKey !== 'translate_diagram')
    }
    return list
  })

  async function handleAIGenerate(options?: {
    generationInstructions?: string
    topicOverride?: string
  }) {
    if (!authStore.isAuthenticated) {
      notify.warning(t('notification.signInToUse'))
      return
    }
    if (diagramStore.collabSessionActive) {
      notify.warning(t('canvas.toolbar.collabLiveAiDisabled'))
      return
    }
    const validation = validateForAutoComplete({
      generationInstructions: options?.generationInstructions,
      topicOverride: options?.topicOverride,
    })
    if (!validation.valid) {
      notify.warning(validation.error || t('canvas.toolbar.cannotGenerate'))
      return
    }

    const stageRaw = authStore.getEffectiveEducationStage()
    const stage = isEducationStage(stageRaw) ? stageRaw : null
    const stageBlock = buildEducationStageInstructions(stage, uiStore.promptLanguage)
    const generationInstructions = mergeGenerationInstructions(
      stageBlock,
      options?.generationInstructions
    )

    const result = await autoComplete({
      promptSuffix: diagramStore.isLearningSheet ? ' 半成品' : undefined,
      generationInstructions,
      topicOverride: options?.topicOverride,
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
      if (useMindMapV2.value) {
        useMindMapSideToolbarState().openTool('waterfall')
      } else {
        eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'toolbar' })
      }
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
        void claimThinkingCoinEvent('learning_sheet_enable')
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
          void claimThinkingCoinEvent('learning_sheet_enable')
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
      runFromCurrentDiagram()
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
