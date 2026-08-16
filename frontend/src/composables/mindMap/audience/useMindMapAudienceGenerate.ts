/**
 * Mind-map AI generate — 专业程度 instructions, not classic 学段.
 */
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useAutoComplete } from '@/composables/editor/useAutoComplete'
import {
  mergeMindMapAudienceInstructions,
  resolveMindMapAudienceInstructions,
} from '@/composables/mindMap/audience/aiContentLevelInstructions'
import { useAiContentLevelStore, useDiagramStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'

export function useMindMapAudienceGenerate() {
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const aiContentLevelStore = useAiContentLevelStore()
  const uiStore = useUIStore()
  const authStore = useAuthStore()
  const { t } = useLanguage()
  const notify = useNotifications()
  const { isGenerating: isAIGenerating, autoComplete, validateForAutoComplete } = useAutoComplete()

  async function handleMindMapAiGenerate(options?: {
    generationInstructions?: string
    topicOverride?: string
  }): Promise<void> {
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

    const levelAtGenerate = aiContentLevelStore.level
    const audienceBlock = resolveMindMapAudienceInstructions(uiStore.promptLanguage)
    const generationInstructions = mergeMindMapAudienceInstructions(
      audienceBlock,
      options?.generationInstructions
    )
    const generatedDiagramKey = aiContentLevelStore.diagramKey(savedDiagramsStore.activeDiagramId)

    const result = await autoComplete({
      promptSuffix: diagramStore.isLearningSheet ? ' 半成品' : undefined,
      generationInstructions,
      topicOverride: options?.topicOverride,
    })
    if (result.success) {
      aiContentLevelStore.markDiagramGenerated(generatedDiagramKey, levelAtGenerate)
      aiContentLevelStore.migrateGeneratedLevel(
        generatedDiagramKey,
        savedDiagramsStore.activeDiagramId
      )
    } else if (result.error) {
      console.error('Mind-map auto-complete failed:', result.error)
    }
  }

  return {
    isAIGenerating,
    handleMindMapAiGenerate,
  }
}
