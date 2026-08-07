<script setup lang="ts">
/**
 * Right-side PPT deck for 图示生图.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ChevronLeft, ChevronRight } from '@lucide/vue'

import ZhiHuiTeacherCaption from '@/components/zhihui/ZhiHuiTeacherCaption.vue'
import { useLanguage } from '@/composables'
import type { ZhihuiGenerationItem } from '@/stores/zhihuiHistory'
import { isZhihuiJobActive } from '@/stores/zhihuiHistory'

const props = withDefaults(
  defineProps<{
    slides: ZhihuiGenerationItem[]
    slideIndex: number
    status?: string | null
    progress?: Record<string, unknown> | null
    errorMessage?: string | null
    /** True while the create request is in flight (before status arrives). */
    starting?: boolean
  }>(),
  {
    status: null,
    progress: null,
    errorMessage: null,
    starting: false,
  }
)

const emit = defineEmits<{
  'update:slideIndex': [index: number]
  resume: []
}>()

const { t } = useLanguage()

const current = computed(() => props.slides[props.slideIndex] ?? null)
const total = computed(() => props.slides.length)
const active = computed(() => props.starting || isZhihuiJobActive(props.status))
const canResume = computed(
  () => props.status === 'failed' || props.status === 'partial'
)

/** Display URL may gain a cache-buster after a failed load (COS eventual consistency). */
const displaySrc = ref('')
const imgLoaded = ref(false)
const imgBroken = ref(false)
let loadRetry = 0
let retryTimer: ReturnType<typeof setTimeout> | null = null

const phaseLabel = computed(() => {
  const status = props.status || ''
  if (status === 'queued') return String(t('zhihui.diagram.phaseQueued'))
  if (status === 'planning') return String(t('zhihui.diagram.phasePlanning'))
  if (status === 'generating') return String(t('zhihui.diagram.phaseGenerating'))
  if (status === 'partial') return String(t('zhihui.diagram.phasePartial'))
  if (status === 'failed') return String(t('zhihui.diagram.phaseFailed'))
  return ''
})

/** Header/body copy when there is no slide yet — never pretend a job is running when idle. */
const emptyStateLabel = computed(() => {
  if (phaseLabel.value) return phaseLabel.value
  if (active.value) return String(t('zhihui.diagram.waitingSlides'))
  return String(t('zhihui.diagram.emptyDeck'))
})

const showBatchProgress = computed(() => {
  const status = props.status || ''
  return (
    props.starting ||
    status === 'queued' ||
    status === 'planning' ||
    status === 'generating' ||
    status === 'partial' ||
    status === 'failed'
  )
})

const batchIndex = computed(() => {
  const raw = props.progress?.batch_index
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null
})

const batchTotal = computed(() => {
  const raw = props.progress?.batch_total
  return typeof raw === 'number' && Number.isFinite(raw) && raw > 0 ? raw : null
})

const progressHint = computed(() => {
  if (batchIndex.value === null || batchTotal.value === null) return ''
  return String(
    t('zhihui.diagram.batchProgress', {
      current: batchIndex.value,
      total: batchTotal.value,
    })
  )
})

const batchPercent = computed(() => {
  if (batchIndex.value === null || batchTotal.value === null || batchTotal.value <= 0) {
    return 0
  }
  return Math.min(100, Math.max(0, (batchIndex.value / batchTotal.value) * 100))
})

const plannedSlideHint = computed(() => {
  const p = props.progress
  if (!p) return ''
  const slideCount = p.slide_count
  const planned = p.planned_slides
  if (
    typeof slideCount === 'number' &&
    typeof planned === 'number' &&
    planned > 0
  ) {
    return String(
      t('zhihui.diagram.slideProgress', { current: slideCount, total: planned })
    )
  }
  return ''
})

function clearRetryTimer(): void {
  if (retryTimer !== null) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
}

function resetImageState(url: string): void {
  clearRetryTimer()
  loadRetry = 0
  imgLoaded.value = false
  imgBroken.value = false
  displaySrc.value = url
}

watch(
  () => [current.value?.id, current.value?.image_url] as const,
  ([id, url]) => {
    if (!id || !url) {
      resetImageState('')
      return
    }
    // Keep a working src when poll only refreshes metadata for the same slide.
    if (displaySrc.value && displaySrc.value.split('?')[0] === url.split('?')[0] && imgLoaded.value) {
      return
    }
    resetImageState(url)
  },
  { immediate: true }
)

function onImgLoad(): void {
  imgLoaded.value = true
  imgBroken.value = false
  loadRetry = 0
}

function onImgError(): void {
  imgLoaded.value = false
  const raw = current.value?.image_url || displaySrc.value || ''
  if (!raw || loadRetry >= 4) {
    imgBroken.value = true
    return
  }
  loadRetry += 1
  clearRetryTimer()
  const delayMs = Math.min(2000, 300 * loadRetry)
  retryTimer = window.setTimeout(() => {
    // Preserve sig/exp (or stable path); only bump a cache-buster.
    try {
      const parsed = new URL(raw, 'https://local.invalid')
      parsed.searchParams.set('retry', String(Date.now()))
      displaySrc.value = `${parsed.pathname}${parsed.search}`
    } catch {
      displaySrc.value = `${raw.split('?')[0]}?retry=${Date.now()}`
    }
  }, delayMs)
}

function prev(): void {
  if (props.slideIndex <= 0) return
  emit('update:slideIndex', props.slideIndex - 1)
}

function next(): void {
  if (props.slideIndex >= total.value - 1) return
  emit('update:slideIndex', props.slideIndex + 1)
}

onBeforeUnmount(() => {
  clearRetryTimer()
})
</script>

<template>
  <div class="zhihui-diagram-deck flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-stone-200 bg-white">
    <div class="flex items-center justify-between border-b border-stone-100 px-3 py-2">
      <button
        type="button"
        class="rounded-md p-1 text-stone-500 hover:bg-stone-50 disabled:opacity-30"
        :disabled="slideIndex <= 0"
        @click="prev"
      >
        <ChevronLeft class="h-4 w-4" />
      </button>
      <div class="min-w-0 flex-1 px-2 text-center text-xs text-stone-500">
        <div class="truncate">
          <template v-if="total > 0">
            {{ slideIndex + 1 }} / {{ total }}
            <span
              v-if="plannedSlideHint && showBatchProgress"
              class="ml-1 text-stone-400"
            >· {{ plannedSlideHint }}</span>
          </template>
          <template v-else>
            {{ emptyStateLabel }}
          </template>
        </div>
        <div
          v-if="showBatchProgress && progressHint"
          class="mt-1 flex flex-col items-center gap-1"
        >
          <div class="h-1 w-28 overflow-hidden rounded-full bg-stone-200">
            <div
              class="h-full rounded-full bg-amber-500 transition-[width] duration-300"
              :style="{ width: `${batchPercent}%` }"
            />
          </div>
          <span class="text-[10px] leading-none text-stone-400">{{ progressHint }}</span>
        </div>
      </div>
      <button
        type="button"
        class="rounded-md p-1 text-stone-500 hover:bg-stone-50 disabled:opacity-30"
        :disabled="slideIndex >= total - 1"
        @click="next"
      >
        <ChevronRight class="h-4 w-4" />
      </button>
    </div>

    <div class="relative flex min-h-0 flex-1 items-center justify-center bg-stone-50 p-3">
      <img
        v-if="displaySrc"
        :key="current?.id || displaySrc"
        :src="displaySrc"
        :alt="current?.slide_title || current?.prompt || 'slide'"
        class="max-h-full max-w-full rounded-lg object-contain shadow-sm transition-opacity duration-200"
        :class="imgLoaded ? 'opacity-100' : 'opacity-0'"
        @load="onImgLoad"
        @error="onImgError"
      >
      <div
        v-if="displaySrc && !imgLoaded && !imgBroken"
        class="absolute inset-0 flex items-center justify-center px-6 text-center text-xs text-stone-400"
      >
        {{ emptyStateLabel }}
      </div>
      <div
        v-else-if="imgBroken"
        class="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-xs text-stone-400"
      >
        <p>{{ t('zhihui.diagram.imageLoadFailed') }}</p>
        <button
          type="button"
          class="rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-50"
          @click="resetImageState(current?.image_url || '')"
        >
          {{ t('zhihui.diagram.retryImage') }}
        </button>
      </div>
      <div
        v-else-if="!displaySrc"
        class="px-6 text-center text-xs text-stone-400"
      >
        <p>{{ emptyStateLabel }}</p>
        <p
          v-if="progressHint"
          class="mt-1"
        >
          {{ progressHint }}
        </p>
        <p
          v-if="errorMessage"
          class="mt-2 text-rose-500"
        >
          {{ errorMessage }}
        </p>
      </div>
      <div
        v-if="active && displaySrc && imgLoaded"
        class="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-white/90 px-3 py-1 text-[11px] text-amber-700 shadow"
      >
        {{ phaseLabel }}
      </div>
    </div>

    <div
      v-if="current?.slide_title || current?.teacher_script || canResume || errorMessage"
      class="zhihui-diagram-deck__caption flex flex-col items-center justify-center gap-2 overflow-visible border-t border-stone-100 px-3 pb-2.5 pt-1"
    >
      <ZhiHuiTeacherCaption
        v-if="current?.slide_title || current?.teacher_script"
        :slide-title="current?.slide_title"
        :teacher-script="current?.teacher_script"
        :auto-play="!active"
      />
      <div
        v-if="canResume"
        class="flex justify-center"
      >
        <button
          type="button"
          class="shrink-0 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-50"
          @click="emit('resume')"
        >
          {{ t('zhihui.diagram.resume') }}
        </button>
      </div>
      <p
        v-if="errorMessage"
        class="max-w-full truncate text-center text-[11px] text-rose-500"
        :title="errorMessage"
      >
        {{ errorMessage }}
      </p>
    </div>
  </div>
</template>
