/**
 * Landing prompt → detect diagram type → load the spec and open the canvas.
 * Shared by the MindGraph landing prompt box and the quick-access remote.
 */
import type { Router } from 'vue-router'

import { dismissReplacingNotification } from '@/composables/core/notifications'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type { useNotifications } from '@/composables/core/useNotifications'
import type { useLandingGenerateGraph } from '@/composables/mindgraph/useLandingGenerateGraph'
import { LANDING_LLM_MODEL, LANDING_PROMPT_MAX_LENGTH } from '@/config/landingQuickAccess'
import { useDiagramStore, useLLMResultsStore } from '@/stores'
import type { DiagramType } from '@/types'

type LandingGeneration = Pick<
  ReturnType<typeof useLandingGenerateGraph>,
  | 'isGenerating'
  | 'generateLandingGraph'
  | 'beginGeneration'
  | 'releaseRun'
  | 'endGeneration'
  | 'isCurrentRun'
>

export async function executeLandingPrompt(options: {
  text: string
  language: string
  t: UseLanguageTranslate
  notify: ReturnType<typeof useNotifications>
  router: Router
  isAuthenticated: boolean
  onAuthRequired: () => void
  generation: LandingGeneration
  canApply?: () => boolean
  onStart?: () => void
  onFinish?: () => void
}): Promise<boolean> {
  const text = options.text.trim()
  if (!text || options.generation.isGenerating.value) {
    return false
  }
  if (!options.isAuthenticated) {
    options.onAuthRequired()
    return false
  }
  if (text.length > LANDING_PROMPT_MAX_LENGTH) {
    options.notify.error(
      options.t('diagramTemplate.promptTooLong', {
        length: text.length,
        max: LANDING_PROMPT_MAX_LENGTH,
      })
    )
    return false
  }

  const run = options.generation.beginGeneration()
  options.onStart?.()
  try {
    const outcome = await options.generation.generateLandingGraph(
      {
        prompt: text,
        language: options.language,
        llm: LANDING_LLM_MODEL,
      },
      run.signal
    )
    if (!outcome.ok || !options.generation.isCurrentRun(run.runId)) {
      return false
    }
    if (options.canApply && !options.canApply()) {
      dismissReplacingNotification()
      return false
    }
    options.generation.releaseRun(run)
    const diagramStore = useDiagramStore()
    diagramStore.clearHistory()
    const spec = outcome.result.spec
    const loaded =
      spec != null && diagramStore.loadFromSpec(spec, outcome.diagramType as DiagramType)
    if (!loaded) {
      options.notify.error(options.t('diagramTemplate.generationFailed'))
      return false
    }
    useLLMResultsStore().reset()
    if (!options.generation.isCurrentRun(run.runId)) {
      return false
    }
    await options.router.push({ path: '/canvas' }).catch(() => undefined)
    return true
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return false
    }
    const msg =
      error instanceof Error ? error.message : options.t('diagramTemplate.generationFailed')
    options.notify.error(msg)
    return false
  } finally {
    options.generation.endGeneration(run)
    options.onFinish?.()
  }
}
