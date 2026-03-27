/**
 * Concept map focus question review — 3-LLM validation + suggestions (canvas flow)
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import {
  FOCUS_MODELS,
  type FocusModel,
  type FocusValidationState,
  streamFocusSuggestions,
  validateFocusQuestionParallel,
} from '@/composables/editor/conceptMapFocusQuestionApi'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { useNotifications } from '@/composables/core/useNotifications'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'

const PAGE_SIZE = 3

function emptyVState(): FocusValidationState {
  return { valid: null, reason: '', error: null, loading: false }
}

export const useConceptMapFocusReviewStore = defineStore('conceptMapFocusReview', () => {
  const diagramStore = useDiagramStore()
  const authStore = useAuthStore()
  const uiStore = useUIStore()
  const notify = useNotifications()

  const validating = ref(false)
  const reviewWaveComplete = ref(false)
  const streamAbortController = ref<AbortController | null>(null)
  const streamPhase = ref<'idle' | 'requesting' | 'streaming'>('idle')

  const validationByModel = ref<Record<FocusModel, FocusValidationState>>({
    qwen: emptyVState(),
    deepseek: emptyVState(),
    doubao: emptyVState(),
  })

  const suggestionRows = ref<Array<{ model: FocusModel; text: string }>>([])
  const suggestionPage = ref(0)
  const loadingMoreSuggestions = ref(false)
  const lastCompletedHash = ref('')
  /** Snapshot of topic text after a successful review; cleared on `clear()` or topic edit */
  const lastValidatedTopicRaw = ref('')

  const visibleSuggestionRows = computed(() => {
    const start = suggestionPage.value * PAGE_SIZE
    return suggestionRows.value.slice(start, start + PAGE_SIZE)
  })

  const totalSuggestionPages = computed(() =>
    Math.max(1, Math.ceil(suggestionRows.value.length / PAGE_SIZE))
  )

  const canPrevSuggestionPage = computed(() => suggestionPage.value > 0)
  const canNextSuggestionPage = computed(
    () => (suggestionPage.value + 1) * PAGE_SIZE < suggestionRows.value.length
  )

  const canLoadMoreSuggestions = computed(
    () =>
      reviewWaveComplete.value &&
      suggestionPage.value === totalSuggestionPages.value - 1 &&
      !loadingMoreSuggestions.value
  )

  /** Topic long enough + not placeholder — Tab badge + allow review */
  const isFocusTopicReady = computed((): boolean => {
    const raw = getTopicRaw()
    if (!raw || raw.trim().length < 4) return false
    if (isPlaceholderText(raw)) return false
    return true
  })

  /** Bottom picker: suggestions only (validation chips live in top bar) */
  const showPicker = computed(() => authStore.isAuthenticated && reviewWaveComplete.value)

  function getTopicRaw(): string {
    const n = diagramStore.data?.nodes?.find((x) => x.id === 'topic' || x.type === 'topic')
    return (n?.text ?? '').trim()
  }

  function resetReviewState(): void {
    for (const m of FOCUS_MODELS) {
      validationByModel.value[m] = emptyVState()
    }
    suggestionRows.value = []
    suggestionPage.value = 0
    reviewWaveComplete.value = false
    loadingMoreSuggestions.value = false
  }

  function clear(): void {
    streamAbortController.value?.abort()
    streamAbortController.value = null
    streamPhase.value = 'idle'
    validating.value = false
    lastCompletedHash.value = ''
    lastValidatedTopicRaw.value = ''
    resetReviewState()
  }

  watch(
    () => {
      const n = diagramStore.data?.nodes?.find((x) => x.id === 'topic' || x.type === 'topic')
      return (n?.text ?? '').trim()
    },
    (next) => {
      if (!lastValidatedTopicRaw.value) return
      if (next !== lastValidatedTopicRaw.value) {
        clear()
      }
    }
  )

  async function runFocusReviewCore(question: string, force: boolean): Promise<void> {
    if (!authStore.isAuthenticated) {
      clear()
      return
    }
    const q = question.trim()
    if (q.length < 4 || isPlaceholderText(q)) {
      clear()
      return
    }
    const hash = `${q.length}:${q.slice(0, 120)}`
    if (!force && hash === lastCompletedHash.value && !validating.value) {
      return
    }

    streamAbortController.value?.abort()
    streamAbortController.value = new AbortController()
    const signal = streamAbortController.value.signal

    validating.value = true
    streamPhase.value = 'requesting'
    resetReviewState()

    const lang = uiStore.promptLanguage

    try {
      const validationPromise = validateFocusQuestionParallel(q, lang, signal)
      const suggestionsPromise = streamFocusSuggestions(
        q,
        lang,
        [],
        signal,
        (model, texts) => {
          streamPhase.value = 'streaming'
          for (const text of texts) {
            suggestionRows.value = [...suggestionRows.value, { model, text }]
          }
        },
        (msg) => notify.warning(msg),
        (msg) => notify.error(msg)
      )

      const [vResult] = await Promise.all([validationPromise, suggestionsPromise])
      if (signal.aborted) return
      validationByModel.value = vResult
      reviewWaveComplete.value = true
      suggestionPage.value = 0
      lastCompletedHash.value = hash
      lastValidatedTopicRaw.value = q
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return
      console.error(e)
      notify.error(i18n.global.t('notification.networkError') as string)
    } finally {
      validating.value = false
      streamPhase.value = 'idle'
      streamAbortController.value = null
    }
  }

  async function runFocusReviewManual(): Promise<void> {
    if (!authStore.isAuthenticated) {
      notify.warning(i18n.global.t('notification.signInToValidateFocus') as string)
      return
    }
    const q = getTopicRaw()
    if (!q.trim() || q.trim().length < 4 || isPlaceholderText(q)) {
      notify.warning(i18n.global.t('notification.focusQuestionTooShort') as string)
      return
    }
    if (validating.value) return
    await runFocusReviewCore(q, true)
  }

  async function loadMoreSuggestions(): Promise<void> {
    const q = getTopicRaw()
    if (q.length < 4 || !authStore.isAuthenticated) return
    streamAbortController.value?.abort()
    streamAbortController.value = new AbortController()
    const signal = streamAbortController.value.signal
    loadingMoreSuggestions.value = true
    const lang = uiStore.promptLanguage
    const avoid = suggestionRows.value.map((r) => r.text)
    try {
      await streamFocusSuggestions(
        q,
        lang,
        avoid,
        signal,
        (model, texts) => {
          for (const text of texts) {
            suggestionRows.value = [...suggestionRows.value, { model, text }]
          }
        },
        (msg) => notify.warning(msg),
        (msg) => notify.error(msg)
      )
      if (
        !signal.aborted &&
        (suggestionPage.value + 1) * PAGE_SIZE <= suggestionRows.value.length
      ) {
        suggestionPage.value += 1
      }
    } catch (e) {
      if (!(e instanceof Error && e.name === 'AbortError')) {
        console.error(e)
        notify.error(i18n.global.t('notification.loadMoreFailed') as string)
      }
    } finally {
      loadingMoreSuggestions.value = false
      streamAbortController.value = null
    }
  }

  function prevSuggestionPage(): void {
    if (canPrevSuggestionPage.value) suggestionPage.value -= 1
  }

  async function nextSuggestionPageOrLoad(): Promise<void> {
    if (canNextSuggestionPage.value) {
      suggestionPage.value += 1
      return
    }
    if (canLoadMoreSuggestions.value) {
      await loadMoreSuggestions()
    }
  }

  function applyTopicText(text: string): void {
    const trimmed = text.trim()
    if (!trimmed) return
    diagramStore.updateNode('topic', { text: trimmed })
    diagramStore.pushHistory('Focus suggestion')
  }

  return {
    validating,
    reviewWaveComplete,
    streamPhase,
    validationByModel,
    suggestionRows,
    suggestionPage,
    loadingMoreSuggestions,
    visibleSuggestionRows,
    totalSuggestionPages,
    canPrevSuggestionPage,
    canNextSuggestionPage,
    canLoadMoreSuggestions,
    isFocusTopicReady,
    showPicker,
    runFocusReviewManual,
    clear,
    prevSuggestionPage,
    nextSuggestionPageOrLoad,
    applyTopicText,
    getTopicRaw,
    PAGE_SIZE,
  }
})
