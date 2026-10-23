/**
 * Seminar MindGraph chip: same one-sentence generate_graph path as the landing prompt,
 * then post the saved diagram into the room as a shared preview.
 */
import { useLanguage, useNotifications } from '@/composables'
import { topicPreviewFromPrompt } from '@/composables/mindgraph/landingGenerateGraphErrors'
import { useLandingGenerateGraph } from '@/composables/mindgraph/useLandingGenerateGraph'
import { LANDING_LLM_MODEL, LANDING_PROMPT_MAX_LENGTH } from '@/config/landingQuickAccess'
import { diagramGenerationLanguages } from '@/diagramBilingual/generationRequest'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { useAuthStore, useSavedDiagramsStore } from '@/stores'
import { authFetch } from '@/utils/api'

export function useSeminarMindgraphPrompt() {
  const { t, promptLanguage } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const savedDiagrams = useSavedDiagramsStore()
  const generation = useLandingGenerateGraph({ t, notify })

  async function generateAndShare(sessionId: string, text: string): Promise<boolean> {
    const prompt = text.trim()
    const session = sessionId.trim()
    if (!prompt || !session || generation.isGenerating.value) {
      return false
    }
    if (!authStore.isAuthenticated) {
      authStore.handleTokenExpired(undefined, undefined)
      return false
    }
    if (prompt.length > LANDING_PROMPT_MAX_LENGTH) {
      notify.errorKey('diagramTemplate.promptTooLong', {
        length: prompt.length,
        max: LANDING_PROMPT_MAX_LENGTH,
      })
      return false
    }

    const run = generation.beginGeneration()
    try {
      const outputLanguages = diagramGenerationLanguages()
      if (outputLanguages.secondaryLanguage) {
        await ensureFontsForLanguageCode(outputLanguages.secondaryLanguage)
      }
      const outcome = await generation.generateLandingGraph(
        {
          prompt,
          language: outputLanguages.language,
          llm: LANDING_LLM_MODEL,
          ...(outputLanguages.secondaryLanguage
            ? { secondary_language: outputLanguages.secondaryLanguage }
            : {}),
        },
        run.signal,
        { announceNavigation: false }
      )
      if (!outcome.ok || !generation.isCurrentRun(run.runId)) {
        return false
      }
      if (!outcome.result.spec) {
        notify.errorKey('diagramTemplate.generationFailed')
        return false
      }
      generation.releaseRun(run)
      const title = topicPreviewFromPrompt(prompt, 80) || t('mindmate.artifacts.diagramFallback')
      const saved = await savedDiagrams.saveDiagram(
        title,
        outcome.diagramType,
        outcome.result.spec,
        promptLanguage.value,
        null,
        'mindmate'
      )
      if (!saved) {
        const detail = savedDiagrams.error
        const limitNotices = [
          t('library.slotFull.title'),
          t('auth.diagramLimitReached', { max: savedDiagrams.maxDiagrams }),
        ]
        if (!detail) {
          notify.errorKey('diagramTemplate.generationFailed')
        } else if (!limitNotices.includes(detail)) {
          notify.error(detail)
        }
        return false
      }
      const response = await authFetch(
        `/api/mindmate/collab/${encodeURIComponent(session)}/share-diagram`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ diagram_id: saved.id }),
        }
      )
      if (!response.ok) {
        notify.errorKey('canvas.ribbon.shareToSeminarFailed')
        return false
      }
      return true
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return false
      }
      const message = error instanceof Error ? error.message : t('diagramTemplate.generationFailed')
      notify.error(message)
      return false
    } finally {
      generation.endGeneration(run)
    }
  }

  return {
    generateAndShare,
    isGenerating: generation.isGenerating,
  }
}
