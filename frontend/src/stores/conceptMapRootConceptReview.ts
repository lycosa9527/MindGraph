/**
 * Concept map root concept — 3-LLM suggestion stream + bottom picker (Tab on root concept node)
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import type { FocusModel } from '@/composables/editor/conceptMapFocusQuestionApi'
import { streamRootConceptSuggestions } from '@/composables/editor/conceptMapRootConceptApi'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { useNotifications } from '@/composables/core/useNotifications'
import { i18n } from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'
import {
  getTopicRootConceptTargetId,
  normalizeAllConceptMapTopicRootLabels,
} from '@/utils/conceptMapTopicRootEdge'

const PAGE_SIZE = 5

export const useConceptMapRootConceptReviewStore = defineStore(
  'conceptMapRootConceptReview',
  () => {
    const diagramStore = useDiagramStore()
    const authStore = useAuthStore()
    const uiStore = useUIStore()
    const notify = useNotifications()

    const streamAbortController = ref<AbortController | null>(null)
    const streamPhase = ref<'idle' | 'requesting' | 'streaming'>('idle')
    const reviewWaveComplete = ref(false)
    const suggestionRows = ref<Array<{ model: FocusModel; text: string }>>([])
    const suggestionPage = ref(0)
    const loadingMoreSuggestions = ref(false)
    const lastCompletedHash = ref('')
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

    function getTopicRaw(): string {
      const n = diagramStore.data?.nodes?.find((x) => x.id === 'topic' || x.type === 'topic')
      return (n?.text ?? '').trim()
    }

    const isRootConceptTabReady = computed((): boolean => {
      const raw = getTopicRaw()
      if (!raw || raw.trim().length < 4) return false
      if (isPlaceholderText(raw)) return false
      return !!getTopicRootConceptTargetId(diagramStore.data?.connections)
    })

    const showPicker = computed(
      () =>
        authStore.isAuthenticated &&
        reviewWaveComplete.value &&
        !!getTopicRootConceptTargetId(diagramStore.data?.connections)
    )

    function resetReviewState(): void {
      suggestionRows.value = []
      suggestionPage.value = 0
      reviewWaveComplete.value = false
      loadingMoreSuggestions.value = false
    }

    function clear(): void {
      streamAbortController.value?.abort()
      streamAbortController.value = null
      streamPhase.value = 'idle'
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

    watch(
      () => getTopicRootConceptTargetId(diagramStore.data?.connections),
      (next, prev) => {
        if (prev !== undefined && next !== prev) {
          clear()
        }
      }
    )

    async function runRootConceptCore(question: string, force: boolean): Promise<void> {
      if (!authStore.isAuthenticated) {
        clear()
        return
      }
      const rootId = getTopicRootConceptTargetId(diagramStore.data?.connections)
      if (!rootId) {
        clear()
        return
      }
      const q = question.trim()
      if (q.length < 4 || isPlaceholderText(q)) {
        clear()
        return
      }
      const hash = `${rootId}:${q.length}:${q.slice(0, 120)}`
      if (!force && hash === lastCompletedHash.value && reviewWaveComplete.value) {
        return
      }

      streamAbortController.value?.abort()
      streamAbortController.value = new AbortController()
      const signal = streamAbortController.value.signal

      streamPhase.value = 'requesting'
      resetReviewState()

      const lang = uiStore.promptLanguage

      try {
        await streamRootConceptSuggestions(
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
        if (signal.aborted) return
        reviewWaveComplete.value = true
        suggestionPage.value = 0
        lastCompletedHash.value = hash
        lastValidatedTopicRaw.value = q
      } catch (e) {
        if (e instanceof Error && e.name === 'AbortError') return
        console.error(e)
        notify.error(i18n.global.t('notification.networkError') as string)
      } finally {
        streamPhase.value = 'idle'
        streamAbortController.value = null
      }
    }

    async function runRootConceptManual(): Promise<void> {
      if (!authStore.isAuthenticated) {
        notify.warning(i18n.global.t('notification.signInToUse') as string)
        return
      }
      if (!getTopicRootConceptTargetId(diagramStore.data?.connections)) {
        notify.warning(i18n.global.t('notification.rootConceptLinkNotFound') as string)
        return
      }
      const q = getTopicRaw()
      if (!q.trim() || q.trim().length < 4 || isPlaceholderText(q)) {
        notify.warning(i18n.global.t('notification.focusQuestionTooShort') as string)
        return
      }
      if (streamPhase.value !== 'idle') return
      await runRootConceptCore(q, true)
    }

    async function loadMoreSuggestions(): Promise<void> {
      const q = getTopicRaw()
      if (q.length < 4 || !authStore.isAuthenticated) return
      if (!getTopicRootConceptTargetId(diagramStore.data?.connections)) return
      streamAbortController.value?.abort()
      streamAbortController.value = new AbortController()
      const signal = streamAbortController.value.signal
      loadingMoreSuggestions.value = true
      streamPhase.value = 'requesting'
      const lang = uiStore.promptLanguage
      const avoid = suggestionRows.value.map((r) => r.text)
      try {
        await streamRootConceptSuggestions(
          q,
          lang,
          avoid,
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
        streamPhase.value = 'idle'
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

    function applyRootConceptText(text: string): void {
      const trimmed = text.trim()
      if (!trimmed) return
      const rootId = getTopicRootConceptTargetId(diagramStore.data?.connections)
      if (!rootId) return
      diagramStore.updateNode(rootId, { text: trimmed })
      diagramStore.pushHistory('Root concept suggestion')
      const connections = diagramStore.data?.connections
      const nodes = diagramStore.data?.nodes
      if (connections && nodes) {
        normalizeAllConceptMapTopicRootLabels(connections, nodes)
      }
    }

    return {
      streamPhase,
      reviewWaveComplete,
      suggestionRows,
      suggestionPage,
      loadingMoreSuggestions,
      visibleSuggestionRows,
      totalSuggestionPages,
      canPrevSuggestionPage,
      canNextSuggestionPage,
      canLoadMoreSuggestions,
      isRootConceptTabReady,
      showPicker,
      runRootConceptManual,
      clear,
      prevSuggestionPage,
      nextSuggestionPageOrLoad,
      applyRootConceptText,
      getTopicRaw,
      PAGE_SIZE,
    }
  }
)
