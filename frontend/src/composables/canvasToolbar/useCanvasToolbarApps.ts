import { computed } from 'vue'

import { useCollabGuestAiGate } from '@/composables/collab/useCollabGuestAiGate'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useAutoComplete } from '@/composables/editor/useAutoComplete'
import { useLearningAiGate } from '@/composables/learningSpace/useLearningAiGate'
import { openConceptMapBrainstorm } from '@/composables/aiBrainstorm/openConceptMapBrainstorm'
import {
  buildEducationStageInstructions,
  isEducationStage,
  mergeGenerationInstructions,
} from '@/constants/educationStage'
import { useDiagramStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'

import {
  canvasVirtualKeyboardOpen,
  ensureCanvasVirtualKeyboardUiVersionSync,
} from './useCanvasVirtualKeyboardOpen'

export function useCanvasToolbarApps() {
  ensureCanvasVirtualKeyboardUiVersionSync()
  const diagramStore = useDiagramStore()
  const uiStore = useUIStore()
  const authStore = useAuthStore()
  const { t } = useLanguage()
  const notify = useNotifications()
  const { isGenerating: isAIGenerating, autoComplete, validateForAutoComplete } = useAutoComplete()
  const { guardCollabGuestAi } = useCollabGuestAiGate()
  const { requireCapability } = useLearningAiGate()

  const isConceptMap = computed(() => diagramStore.type === 'concept_map')

  async function handleAIGenerate(options?: {
    generationInstructions?: string
    topicOverride?: string
    isLearningSheet?: boolean
  }) {
    if (diagramStore.type === 'concept_map') {
      openConceptMapBrainstorm()
      return
    }
    if (!authStore.isAuthenticated) {
      notify.warningKey('notification.signInToUse')
      return
    }
    if (!requireCapability('topic_generate')) return
    if (!guardCollabGuestAi()) {
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
      promptSuffix:
        diagramStore.isLearningSheet || options?.isLearningSheet ? ' 半成品' : undefined,
      generationInstructions,
      topicOverride: options?.topicOverride,
    })
    if (!result.success && result.error) {
      console.error('Auto-complete failed:', result.error)
    }
  }

  function handleConceptGeneration() {
    openConceptMapBrainstorm()
  }

  return {
    isAIGenerating,
    isConceptMap,
    virtualKeyboardOpen: canvasVirtualKeyboardOpen,
    handleAIGenerate,
    handleConceptGeneration,
  }
}
