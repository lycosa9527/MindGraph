<script setup lang="ts">
/**
 * Right-side PPT deck for 图示生图.
 */
import { computed } from 'vue'

import { ChevronLeft, ChevronRight } from '@lucide/vue'

import { useLanguage } from '@/composables'
import type { ZhihuiGenerationItem } from '@/stores/zhihuiHistory'
import { isZhihuiJobActive } from '@/stores/zhihuiHistory'

const props = defineProps<{
  slides: ZhihuiGenerationItem[]
  slideIndex: number
  status?: string | null
  progress?: Record<string, unknown> | null
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  'update:slideIndex': [index: number]
  resume: []
}>()

const { t } = useLanguage()

const current = computed(() => props.slides[props.slideIndex] ?? null)
const total = computed(() => props.slides.length)
const active = computed(() => isZhihuiJobActive(props.status))
const canResume = computed(
  () => props.status === 'failed' || props.status === 'partial'
)

const phaseLabel = computed(() => {
  const status = props.status || ''
  if (status === 'queued') return String(t('zhihui.diagram.phaseQueued'))
  if (status === 'planning') return String(t('zhihui.diagram.phasePlanning'))
  if (status === 'generating') return String(t('zhihui.diagram.phaseGenerating'))
  if (status === 'partial') return String(t('zhihui.diagram.phasePartial'))
  if (status === 'failed') return String(t('zhihui.diagram.phaseFailed'))
  return ''
})

const progressHint = computed(() => {
  const p = props.progress
  if (!p) return ''
  const batchIndex = p.batch_index
  const batchTotal = p.batch_total
  if (typeof batchIndex === 'number' && typeof batchTotal === 'number' && batchTotal > 0) {
    return String(
      t('zhihui.diagram.batchProgress', { current: batchIndex, total: batchTotal })
    )
  }
  return ''
})

function prev(): void {
  if (props.slideIndex <= 0) return
  emit('update:slideIndex', props.slideIndex - 1)
}

function next(): void {
  if (props.slideIndex >= total.value - 1) return
  emit('update:slideIndex', props.slideIndex + 1)
}
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
      <div class="text-xs text-stone-500">
        <template v-if="total > 0">
          {{ slideIndex + 1 }} / {{ total }}
        </template>
        <template v-else>
          {{ phaseLabel || t('zhihui.diagram.waitingSlides') }}
        </template>
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
        v-if="current?.image_url"
        :src="current.image_url"
        :alt="current.slide_title || current.prompt || 'slide'"
        class="max-h-full max-w-full rounded-lg object-contain shadow-sm"
      >
      <div
        v-else
        class="px-6 text-center text-xs text-stone-400"
      >
        <p>{{ phaseLabel || t('zhihui.diagram.waitingSlides') }}</p>
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
        v-if="active && current?.image_url"
        class="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-white/90 px-3 py-1 text-[11px] text-amber-700 shadow"
      >
        {{ phaseLabel }}
      </div>
    </div>

    <div
      v-if="current?.slide_title || canResume"
      class="flex items-center justify-center gap-3 border-t border-stone-100 px-3 py-2"
    >
      <p
        v-if="current?.slide_title"
        class="text-center text-xs text-stone-600"
      >
        {{ current.slide_title }}
      </p>
      <button
        v-if="canResume"
        type="button"
        class="shrink-0 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-50"
        @click="emit('resume')"
      >
        {{ t('zhihui.diagram.resume') }}
      </button>
    </div>
  </div>
</template>
