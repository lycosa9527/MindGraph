<script setup lang="ts">
/**
 * Knowledge Space landing card — RAG + wiki pipeline explainer and live status.
 */
import { computed } from 'vue'

import { BookOpen, BookMarked, Layers, Search, Sparkles, Upload } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { usePackages } from '@/composables/fileCenter/useFileCenter'

const { t } = useLanguage()
const packagesQuery = usePackages()
const packages = computed(() => packagesQuery.data.value?.packages ?? [])
const wikiCompileEnabled = computed(
  () => packagesQuery.data.value?.wiki_compile_enabled ?? false
)

const ragReadyCount = computed(
  () => packages.value.filter((pkg) => pkg.rag_status === 'completed').length
)
const wikiReadyCount = computed(
  () => packages.value.filter((pkg) => pkg.wiki_status === 'ready').length
)
const wikiPendingCount = computed(
  () => packages.value.filter((pkg) => pkg.wiki_status === 'pending').length
)
const processingCount = computed(
  () => packages.value.filter((pkg) => pkg.rag_status === 'processing').length
)

const steps = [
  { key: 'step1', icon: Upload },
  { key: 'step2', icon: Layers },
  { key: 'step3', icon: BookMarked },
  { key: 'step4', icon: Search },
  { key: 'step5', icon: Sparkles },
] as const

type PipelineTone = 'neutral' | 'active' | 'success' | 'muted'

interface PipelineRow {
  key: string
  tone: PipelineTone
  detail: string
}

const pipelineRows = computed((): PipelineRow[] => {
  const rows: PipelineRow[] = []

  if (processingCount.value > 0) {
    rows.push({
      key: 'ragProcessing',
      tone: 'active',
      detail: t('knowledge.pipeline.ragProcessingDetail', { count: processingCount.value }),
    })
  } else if (ragReadyCount.value > 0) {
    rows.push({
      key: 'ragReady',
      tone: 'success',
      detail: t('knowledge.pipeline.ragReadyDetail', { count: ragReadyCount.value }),
    })
  } else {
    rows.push({
      key: 'ragIdle',
      tone: 'neutral',
      detail: t('knowledge.pipeline.ragIdleDetail'),
    })
  }

  if (!wikiCompileEnabled.value) {
    rows.push({
      key: 'wikiDisabled',
      tone: 'muted',
      detail: t('knowledge.pipeline.wikiDisabledDetail'),
    })
  } else if (wikiPendingCount.value > 0) {
    rows.push({
      key: 'wikiPending',
      tone: 'active',
      detail: t('knowledge.pipeline.wikiPendingDetail', { count: wikiPendingCount.value }),
    })
  } else if (wikiReadyCount.value > 0) {
    rows.push({
      key: 'wikiReady',
      tone: 'success',
      detail: t('knowledge.pipeline.wikiReadyDetail', { count: wikiReadyCount.value }),
    })
  } else {
    rows.push({
      key: 'wikiIdle',
      tone: 'neutral',
      detail: t('knowledge.pipeline.wikiIdleDetail'),
    })
  }

  return rows
})

const toneClasses: Record<PipelineTone, string> = {
  neutral: 'border-slate-200 bg-white text-slate-600',
  active: 'border-amber-200 bg-amber-50 text-amber-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  muted: 'border-slate-200 bg-slate-50 text-slate-500',
}
</script>

<template>
  <div class="mb-6 rounded-xl border border-slate-200 bg-white">
    <div class="border-b border-slate-100 px-5 py-4">
      <div class="flex items-start gap-3">
        <BookOpen
          class="mt-0.5 h-5 w-5 shrink-0 text-blue-500"
          :stroke-width="2"
        />
        <div>
          <h3 class="text-sm font-semibold text-slate-800">
            {{ t('knowledge.ragGuide.title') }}
          </h3>
          <p class="mt-1 text-sm leading-relaxed text-slate-500">
            {{ t('knowledge.ragGuide.subtitle') }}
          </p>
        </div>
      </div>
    </div>

    <div class="border-b border-slate-100 px-5 py-4">
      <h4 class="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {{ t('knowledge.pipeline.title') }}
      </h4>
      <div class="mt-3 grid gap-2 sm:grid-cols-2">
        <div
          v-for="row in pipelineRows"
          :key="row.key"
          class="rounded-lg border px-3 py-2.5"
          :class="toneClasses[row.tone]"
        >
          <p class="text-xs font-medium">
            {{ t(`knowledge.pipeline.${row.key}`) }}
          </p>
          <p class="mt-1 text-xs leading-relaxed opacity-90">
            {{ row.detail }}
          </p>
        </div>
      </div>
    </div>

    <ol class="divide-y divide-slate-100 px-5 py-2">
      <li
        v-for="(step, index) in steps"
        :key="step.key"
        class="flex gap-3 py-3.5"
      >
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600"
        >
          {{ index + 1 }}
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <component
              :is="step.icon"
              class="h-4 w-4 shrink-0 text-slate-400"
              :stroke-width="2"
            />
            <h4 class="text-sm font-medium text-slate-800">
              {{ t(`knowledge.ragGuide.${step.key}.title`) }}
            </h4>
          </div>
          <p class="mt-1 text-sm leading-relaxed text-slate-500">
            {{ t(`knowledge.ragGuide.${step.key}.body`) }}
          </p>
        </div>
      </li>
    </ol>

    <div class="border-t border-slate-100 bg-slate-50/80 px-5 py-3.5">
      <p class="text-xs leading-relaxed text-slate-500">
        {{ t('knowledge.ragGuide.footer') }}
      </p>
    </div>
  </div>
</template>
