<script setup lang="ts">
/**
 * Standard-mode gate: 3-LLM validation (once, may disagree) + rolling suggestions
 * (5 per page, - / = like label picker). Validation and suggestions run in parallel.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElAlert, ElButton, ElInput, ElTooltip } from 'element-plus'

import { Check, CircleSlash, Equal, Loader2, Minus } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { getLLMColor } from '@/config/llmModelColors'
import { useUIStore } from '@/stores/ui'
import { authFetch } from '@/utils/api'

const FOCUS_MODELS = ['qwen', 'deepseek', 'doubao'] as const
type FocusModel = (typeof FOCUS_MODELS)[number]

const MODEL_LABELS: Record<FocusModel, string> = {
  qwen: 'Qwen',
  deepseek: 'DeepSeek',
  doubao: 'Doubao',
}

const PAGE_SIZE = 5

const props = defineProps<{
  isAuthenticated: boolean
}>()

const emit = defineEmits<{
  confirm: [text: string]
}>()

const { t, promptLanguage } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()

function llmValidateChipSurface(m: FocusModel): Record<string, string> {
  const c = getLLMColor(m, uiStore.isDark)
  if (!c) return {}
  return {
    backgroundColor: c.bg,
    borderColor: c.border,
  }
}

function llmValidateChipLabelStyle(m: FocusModel): Record<string, string> {
  const c = getLLMColor(m, uiStore.isDark)
  if (!c) return {}
  return { color: c.text }
}

/** User-typed wording; persists when browsing suggestion pages or picking slots. */
const ownQuestion = ref('')

const validating = ref(false)
const skipAi = ref(false)
/** First wave: validate JSON done + suggestions SSE `end` */
const reviewWaveComplete = ref(false)
const streamAbortController = ref<AbortController | null>(null)

type VState = {
  valid: boolean | null
  reason: string
  error: string | null
  loading: boolean
}

function emptyVState(): VState {
  return { valid: null, reason: '', error: null, loading: false }
}

const validationByModel = ref<Record<FocusModel, VState>>({
  qwen: emptyVState(),
  deepseek: emptyVState(),
  doubao: emptyVState(),
})

const suggestionRows = ref<Array<{ model: FocusModel; text: string }>>([])
const suggestionPage = ref(0)
const loadingMoreSuggestions = ref(false)
const suggestionsStreamEnded = ref(false)

const selectedSlot = ref(0)

const labels = computed(() => ({
  title: t('focusQuestion.title'),
  help: t('focusQuestion.help'),
  validate: t('focusQuestion.validate'),
  skip: t('focusQuestion.skip'),
  confirm: t('focusQuestion.confirm'),
  loginHint: t('focusQuestion.loginHint'),
  needValidate: t('focusQuestion.needValidate'),
  tooShort: t('focusQuestion.tooShort'),
  suggestionsHint: t('focusQuestion.suggestionsHint'),
  suggestionsEmpty: t('focusQuestion.suggestionsEmpty'),
}))

const visibleRows = computed(() => {
  const start = suggestionPage.value * PAGE_SIZE
  return suggestionRows.value.slice(start, start + PAGE_SIZE)
})

/**
 * Tab-style display: 0 = ownQuestion; 1–5 = visibleRows[slot-1]. Read-only; user edits go through onDraftInput.
 */
const draft = computed(() => {
  if (selectedSlot.value === 0) {
    return ownQuestion.value
  }
  const row = visibleRows.value[selectedSlot.value - 1]
  return row?.text ?? ownQuestion.value
})

function onDraftInput(val: string) {
  ownQuestion.value = val
  selectedSlot.value = 0
}

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

function vState(m: FocusModel): VState {
  return validationByModel.value[m] ?? emptyVState()
}

function resetReviewState() {
  for (const m of FOCUS_MODELS) {
    validationByModel.value[m] = emptyVState()
  }
  suggestionRows.value = []
  suggestionPage.value = 0
  reviewWaveComplete.value = false
  suggestionsStreamEnded.value = false
  selectedSlot.value = 0
  loadingMoreSuggestions.value = false
}

watch(ownQuestion, () => {
  skipAi.value = false
  resetReviewState()
})

const canTryValidate = computed(
  () => draft.value.trim().length >= 4 && !validating.value && !loadingMoreSuggestions.value
)

const canConfirm = computed(() => {
  const q = draft.value.trim()
  if (q.length < 2) return false
  if (!props.isAuthenticated) return true
  if (skipAi.value) return true
  if (!reviewWaveComplete.value) return false
  if (selectedSlot.value === 0) return true
  const idx = selectedSlot.value - 1
  return idx >= 0 && idx < visibleRows.value.length
})

watch(visibleRows, (rows) => {
  if (selectedSlot.value === 0) return
  const n = rows.length
  if (selectedSlot.value > n) {
    selectedSlot.value = n > 0 ? n : 0
  }
})

function parseSseDataLine(line: string): Record<string, unknown> | null {
  const trimmed = line.trim()
  if (!trimmed.startsWith('data: ')) return null
  try {
    return JSON.parse(trimmed.slice(6)) as Record<string, unknown>
  } catch {
    return null
  }
}

async function runValidateParallel(
  question: string,
  lang: string,
  signal: AbortSignal
): Promise<void> {
  for (const m of FOCUS_MODELS) {
    validationByModel.value[m] = {
      ...emptyVState(),
      loading: true,
    }
  }
  const response = await authFetch('/api/concept_map/focus_question_review/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, language: lang }),
    signal,
  })
  if (!response.ok) {
    const errBody = (await response.json().catch(() => ({}))) as { detail?: string }
    const msg =
      typeof errBody.detail === 'string'
        ? errBody.detail
        : t('focusQuestion.validationRequestFailed')
    notify.error(msg)
    for (const m of FOCUS_MODELS) {
      validationByModel.value[m] = {
        valid: false,
        reason: '',
        error: msg,
        loading: false,
      }
    }
    return
  }
  const data = (await response.json()) as {
    results?: Array<{
      model: string
      valid: boolean
      reason: string
      error: string | null
    }>
  }
  const list = data.results ?? []
  for (const m of FOCUS_MODELS) {
    const row = list.find((r) => r.model === m)
    if (row && !row.error) {
      validationByModel.value[m] = {
        valid: Boolean(row.valid),
        reason: (row.reason ?? '').trim(),
        error: null,
        loading: false,
      }
    } else if (row?.error) {
      validationByModel.value[m] = {
        valid: false,
        reason: '',
        error: row.error,
        loading: false,
      }
    } else {
      validationByModel.value[m] = {
        valid: false,
        reason: '',
        error: t('focusQuestion.noResult'),
        loading: false,
      }
    }
  }
}

async function consumeSuggestionsStream(
  question: string,
  lang: string,
  avoid: string[],
  append: boolean,
  signal: AbortSignal
): Promise<void> {
  if (!append) {
    suggestionRows.value = []
    suggestionsStreamEnded.value = false
  }
  const response = await authFetch('/api/concept_map/focus_question_review/suggestions/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      language: lang,
      avoid: avoid.length ? avoid : undefined,
    }),
    signal,
  })
  if (!response.ok) {
    const errBody = (await response.json().catch(() => ({}))) as { detail?: string }
    notify.error(
      typeof errBody.detail === 'string'
        ? errBody.detail
        : t('focusQuestion.suggestionsRequestFailed')
    )
    suggestionsStreamEnded.value = true
    return
  }
  const reader = response.body?.getReader()
  if (!reader) {
    notify.error(t('focusQuestion.cannotReadStream'))
    suggestionsStreamEnded.value = true
    return
  }
  const decoder = new TextDecoder()
  let lineBuffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      lineBuffer += decoder.decode(value, { stream: true })
      const lines = lineBuffer.split('\n')
      lineBuffer = lines.pop() ?? ''
      for (const line of lines) {
        const payload = parseSseDataLine(line.replace(/\r$/, ''))
        if (!payload) continue
        const ev = payload.event as string
        if (ev === 'model_suggestions') {
          const model = payload.model
          const sug = payload.suggestions
          if (
            typeof model === 'string' &&
            (FOCUS_MODELS as readonly string[]).includes(model) &&
            Array.isArray(sug)
          ) {
            const fm = model as FocusModel
            const texts = sug.map((s) => String(s).trim()).filter(Boolean)
            for (const text of texts) {
              suggestionRows.value = [...suggestionRows.value, { model: fm, text }]
            }
          }
        } else if (ev === 'model_error' && typeof payload.message === 'string') {
          notify.warning(`${payload.model ?? '?'}: ${payload.message}`)
        } else if (ev === 'error' && typeof payload.message === 'string') {
          notify.error(payload.message)
        } else if (ev === 'end') {
          suggestionsStreamEnded.value = true
        }
      }
    }
    if (lineBuffer.trim()) {
      const tail = parseSseDataLine(lineBuffer.replace(/\r$/, ''))
      if (tail?.event === 'end') {
        suggestionsStreamEnded.value = true
      }
    }
  } finally {
    reader.releaseLock()
  }
  if (!suggestionsStreamEnded.value) {
    suggestionsStreamEnded.value = true
  }
}

async function runValidation() {
  const q = draft.value.trim()
  if (q.length < 4) {
    notify.warning(labels.value.tooShort)
    return
  }
  if (!props.isAuthenticated) return

  streamAbortController.value?.abort()
  streamAbortController.value = new AbortController()
  const signal = streamAbortController.value.signal

  validating.value = true
  skipAi.value = false
  resetReviewState()
  const lang = promptLanguage.value

  try {
    await Promise.all([
      runValidateParallel(q, lang, signal),
      consumeSuggestionsStream(q, lang, [], false, signal),
    ])
    if (!signal.aborted) {
      reviewWaveComplete.value = true
      suggestionPage.value = 0
      selectedSlot.value = 0
    }
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') {
      return
    }
    console.error(e)
    notify.error(t('focusQuestion.networkError'))
  } finally {
    validating.value = false
  }
}

async function loadMoreSuggestions() {
  const q = draft.value.trim()
  if (q.length < 4 || !props.isAuthenticated) return
  streamAbortController.value?.abort()
  streamAbortController.value = new AbortController()
  const signal = streamAbortController.value.signal
  loadingMoreSuggestions.value = true
  const lang = promptLanguage.value
  const avoid = suggestionRows.value.map((r) => r.text)
  try {
    await consumeSuggestionsStream(q, lang, avoid, true, signal)
    if (!signal.aborted && (suggestionPage.value + 1) * PAGE_SIZE <= suggestionRows.value.length) {
      suggestionPage.value += 1
    }
  } catch (e) {
    if (!(e instanceof Error && e.name === 'AbortError')) {
      console.error(e)
      notify.error(t('focusQuestion.loadMoreFailed'))
    }
  } finally {
    loadingMoreSuggestions.value = false
  }
}

function prevSuggestionPage() {
  if (canPrevSuggestionPage.value) suggestionPage.value -= 1
}

async function nextSuggestionPageOrLoad() {
  if (canNextSuggestionPage.value) {
    suggestionPage.value += 1
    return
  }
  if (canLoadMoreSuggestions.value) {
    await loadMoreSuggestions()
  }
}

function doSkipAi() {
  streamAbortController.value?.abort()
  skipAi.value = true
  resetReviewState()
  reviewWaveComplete.value = true
}

function handlePickerKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (target?.tagName === 'INPUT' || target?.tagName === 'TEXTAREA') return
  if (target?.isContentEditable) return

  if (!props.isAuthenticated || skipAi.value) return
  if (!reviewWaveComplete.value) return

  if (event.key === '-') {
    event.preventDefault()
    event.stopPropagation()
    prevSuggestionPage()
    return
  }
  if (event.key === '=') {
    event.preventDefault()
    event.stopPropagation()
    void nextSuggestionPageOrLoad()
    return
  }

  const num =
    event.key === '0'
      ? 0
      : event.key === '1'
        ? 1
        : event.key === '2'
          ? 2
          : event.key === '3'
            ? 3
            : event.key === '4'
              ? 4
              : event.key === '5'
                ? 5
                : -1
  if (num === 0) {
    event.preventDefault()
    event.stopPropagation()
    selectedSlot.value = 0
    return
  }
  if (num >= 1 && num <= 5) {
    if (num - 1 < visibleRows.value.length) {
      event.preventDefault()
      event.stopPropagation()
      selectedSlot.value = num
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handlePickerKeydown, { capture: true })
})
onUnmounted(() => {
  streamAbortController.value?.abort()
  window.removeEventListener('keydown', handlePickerKeydown, { capture: true })
})

function confirm() {
  const q = draft.value.trim()
  if (q.length < 2) {
    notify.warning(labels.value.tooShort)
    return
  }
  if (props.isAuthenticated && !skipAi.value && !reviewWaveComplete.value) {
    notify.warning(labels.value.needValidate)
    return
  }
  emit('confirm', q)
}
</script>

<template>
  <div
    class="focus-modal rounded-2xl shadow-2xl border border-gray-200/90 dark:border-gray-600 bg-white dark:bg-gray-900 max-w-2xl w-full p-6 max-h-[min(90vh,720px)] overflow-y-auto"
    role="dialog"
    aria-modal="true"
    :aria-label="labels.title"
  >
    <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2 leading-snug">
      {{ labels.title }}
    </h2>
    <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed mb-4">
      {{ labels.help }}
    </p>

    <ElInput
      :model-value="draft"
      type="textarea"
      :rows="4"
      :placeholder="t('focusQuestion.placeholder')"
      class="mb-3"
      @update:model-value="onDraftInput"
    />

    <ElAlert
      v-if="!isAuthenticated"
      type="info"
      :closable="false"
      class="mb-3"
      show-icon
    >
      <span class="text-xs">{{ labels.loginHint }}</span>
    </ElAlert>

    <!-- One row: AI检验 left, 跳过 centered, 确认 right (skip uses overlay so it stays true center) -->
    <div class="relative flex w-full items-center gap-2 mb-2 min-h-10">
      <div class="flex min-w-0 flex-1 items-center justify-start">
        <ElButton
          v-if="isAuthenticated"
          type="primary"
          :disabled="!canTryValidate"
          @click="runValidation"
        >
          {{ labels.validate }}
        </ElButton>
      </div>
      <div class="flex min-w-0 flex-1 items-center justify-end">
        <ElButton
          type="success"
          :disabled="!canConfirm"
          @click="confirm"
        >
          {{ labels.confirm }}
        </ElButton>
      </div>
      <div
        v-if="isAuthenticated && !skipAi"
        class="pointer-events-none absolute inset-0 flex items-center justify-center"
      >
        <ElButton
          class="pointer-events-auto"
          text
          type="info"
          @click="doSkipAi"
        >
          {{ labels.skip }}
        </ElButton>
      </div>
    </div>

    <!-- 3-LLM verdict chips: below action row (Qwen / DeepSeek / Doubao) -->
    <div
      v-if="isAuthenticated && !skipAi && (validating || reviewWaveComplete)"
      class="mb-3"
    >
      <div class="flex flex-wrap gap-2">
        <div
          v-for="m in FOCUS_MODELS"
          :key="m"
          class="flex items-center gap-1.5 rounded-lg border border-solid px-2.5 py-1.5"
          :style="llmValidateChipSurface(m)"
        >
          <span
            class="text-xs font-semibold"
            :style="llmValidateChipLabelStyle(m)"
            >{{ MODEL_LABELS[m] }}</span
          >
          <Loader2
            v-if="vState(m).loading"
            class="w-4 h-4 animate-spin text-blue-500 shrink-0"
          />
          <template v-else-if="vState(m).error">
            <ElTooltip
              :content="`${MODEL_LABELS[m]} · ${vState(m).error ?? ''}`"
              placement="top"
            >
              <CircleSlash class="w-4 h-4 text-amber-600 shrink-0 cursor-help" />
            </ElTooltip>
          </template>
          <template v-else-if="vState(m).valid === true">
            <ElTooltip
              :content="`${MODEL_LABELS[m]} · ${vState(m).reason || t('focusQuestion.passLabel')}`"
              placement="top"
            >
              <Check class="w-4 h-4 text-emerald-600 shrink-0 cursor-help" />
            </ElTooltip>
          </template>
          <template v-else-if="vState(m).valid === false">
            <ElTooltip
              :content="`${MODEL_LABELS[m]} · ${vState(m).reason || t('focusQuestion.weakLabel')}`"
              placement="top"
            >
              <CircleSlash class="w-4 h-4 text-red-600 shrink-0 cursor-help" />
            </ElTooltip>
          </template>
        </div>
      </div>
    </div>

    <!-- Suggestions: vertical list (tab-style paging); − / = top-right -->
    <div
      v-if="isAuthenticated && (reviewWaveComplete || skipAi) && !skipAi"
      class="mt-4 pt-4 border-t border-gray-200/80 dark:border-gray-600/80"
    >
      <div class="flex items-start justify-between gap-3 mb-2">
        <p
          class="text-xs font-medium text-gray-500 dark:text-gray-400 flex-1 min-w-0 pr-2 leading-snug"
        >
          {{ labels.suggestionsHint }}
        </p>
        <div
          class="flex items-center gap-1 shrink-0"
          role="toolbar"
          :aria-label="t('focusQuestion.pagingAria')"
        >
          <button
            type="button"
            class="inline-flex items-center justify-center w-8 h-8 rounded-md border border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-35 disabled:pointer-events-none"
            :disabled="!canPrevSuggestionPage"
            aria-label="Previous page"
            @click="prevSuggestionPage"
          >
            <Minus class="w-4 h-4 text-gray-600 dark:text-gray-300" />
          </button>
          <span
            v-if="totalSuggestionPages > 1 || suggestionRows.length > 0"
            class="tabular-nums text-[11px] text-gray-500 dark:text-gray-400 px-0.5 min-w-[2.25rem] text-center"
          >
            {{ suggestionPage + 1 }}/{{ totalSuggestionPages }}
          </span>
          <button
            type="button"
            class="inline-flex items-center justify-center w-8 h-8 rounded-md border border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-40 disabled:pointer-events-none"
            :disabled="loadingMoreSuggestions"
            aria-label="Next page or load more"
            @click="nextSuggestionPageOrLoad"
          >
            <Equal class="w-4 h-4 text-gray-600 dark:text-gray-300" />
          </button>
          <Loader2
            v-if="loadingMoreSuggestions"
            class="w-4 h-4 animate-spin text-gray-500 shrink-0 ml-0.5"
          />
        </div>
      </div>

      <p
        v-if="!validating && !loadingMoreSuggestions && suggestionRows.length === 0"
        class="text-xs text-amber-700 dark:text-amber-300 mb-2"
      >
        {{ labels.suggestionsEmpty }}
      </p>

      <ul
        class="flex flex-col gap-2 mb-1 list-none p-0 m-0"
        role="listbox"
        :aria-label="t('focusQuestion.alternativesAria')"
      >
        <li>
          <button
            type="button"
            class="focus-row flex w-full min-w-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors whitespace-nowrap"
            :class="
              selectedSlot === 0
                ? 'border-blue-500 bg-blue-50/90 dark:bg-blue-950/40 ring-1 ring-blue-400/50'
                : 'border-gray-200 dark:border-gray-600 bg-gray-50/50 dark:bg-gray-800/50 hover:border-blue-300 dark:hover:border-blue-600'
            "
            :title="ownQuestion.trim() || t('focusQuestion.emptyOwn')"
            @click="selectedSlot = 0"
          >
            <span
              class="shrink-0 font-mono text-xs font-semibold tabular-nums text-blue-600 dark:text-blue-400"
              >0</span
            >
            <span class="min-w-0 flex-1 truncate text-left text-gray-800 dark:text-gray-100">{{
              ownQuestion.trim() || t('focusQuestion.emptyOwn')
            }}</span>
          </button>
        </li>
        <li
          v-for="(row, idx) in visibleRows"
          :key="`${suggestionPage}-${idx}-${row.text.slice(0, 24)}`"
        >
          <button
            type="button"
            class="focus-row flex w-full min-w-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors whitespace-nowrap"
            :class="
              selectedSlot === idx + 1
                ? 'border-blue-500 bg-blue-50/90 dark:bg-blue-950/40 ring-1 ring-blue-400/50'
                : 'border-gray-200 dark:border-gray-600 bg-gray-50/50 dark:bg-gray-800/50 hover:border-blue-300 dark:hover:border-blue-600'
            "
            :title="row.text"
            @click="selectedSlot = idx + 1"
          >
            <span
              class="shrink-0 font-mono text-xs font-semibold tabular-nums text-blue-600 dark:text-blue-400"
              >{{ idx + 1 }}</span
            >
            <span class="min-w-0 flex-1 truncate text-left text-gray-800 dark:text-gray-100">{{
              row.text
            }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.focus-modal :deep(.el-textarea__inner) {
  font-size: 13px;
}
</style>
