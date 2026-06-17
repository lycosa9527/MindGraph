<script setup lang="ts">
/**
 * Mind map one-sentence generate panel — long-form requirements + inspiration chips.
 */
import { ref } from 'vue'

import { Lightbulb, Sparkles, X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useDiagramStore } from '@/stores'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const diagramStore = useDiagramStore()
const { isAIGenerating } = useCanvasToolbarApps()
const { runOneSentenceGenerate } = useMindMapSideToolbarState()

const requirements = ref('')

const exampleKeys = [
  'canvas.mindMapOneSentence.example1',
  'canvas.mindMapOneSentence.example2',
  'canvas.mindMapOneSentence.example3',
] as const

function handleClose(): void {
  emit('close')
}

function applyExample(key: (typeof exampleKeys)[number]): void {
  requirements.value = t(key)
}

function handleGenerate(): void {
  runOneSentenceGenerate(requirements.value.trim() || undefined)
}
</script>

<template>
  <aside
    class="mind-map-one-sentence-panel pointer-events-auto absolute inset-y-3 left-3 z-40 flex w-80 flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm"
    :aria-label="t('canvas.mindMapSideToolbar.oneSentence')"
  >
    <header class="flex shrink-0 items-center justify-between gap-2 border-b border-slate-100 px-3 py-3">
      <h3 class="truncate text-sm font-semibold text-slate-800">
        {{ t('canvas.mindMapSideToolbar.oneSentence') }}
      </h3>
      <button
        type="button"
        class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
        :aria-label="t('canvas.mindMapSideToolbar.closePanel')"
        @click="handleClose"
      >
        <X
          class="h-4 w-4"
          :stroke-width="2"
        />
      </button>
    </header>

    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-3 py-3">
      <p class="text-xs leading-relaxed text-slate-600">
        {{ t('canvas.mindMapOneSentence.intro') }}
      </p>

      <textarea
        v-model="requirements"
        class="mind-map-one-sentence-panel__textarea w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm leading-relaxed text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-violet-400 focus:outline-none focus:ring-2 focus:ring-violet-100"
        :placeholder="t('canvas.mindMapOneSentence.requirementsPlaceholder')"
        rows="4"
      />

      <section class="shrink-0">
        <div class="mb-2 flex items-center gap-1.5 text-xs font-medium text-slate-600">
          <Lightbulb
            class="h-3.5 w-3.5 text-amber-500"
            :stroke-width="2"
          />
          <span>{{ t('canvas.mindMapOneSentence.examplesTitle') }}</span>
        </div>
        <div class="flex flex-col gap-1.5">
          <button
            v-for="key in exampleKeys"
            :key="key"
            type="button"
            class="one-sentence-inspiration-chip text-left"
            @click="applyExample(key)"
          >
            {{ t(key) }}
          </button>
        </div>

        <button
          type="button"
          class="one-sentence-generate-btn mt-3 w-full"
          :disabled="isAIGenerating || diagramStore.collabSessionActive"
          @click="handleGenerate"
        >
          <Sparkles
            class="h-4 w-4 shrink-0"
            :stroke-width="2"
          />
          {{
            isAIGenerating
              ? t('canvas.toolbar.aiGenerating')
              : t('canvas.mindMapOneSentence.generateButton')
          }}
        </button>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.mind-map-one-sentence-panel {
  max-height: calc(100% - 1.5rem);
}

.mind-map-one-sentence-panel__textarea {
  min-height: 96px;
}

.one-sentence-inspiration-chip {
  width: 100%;
  padding: 9px 11px;
  border: 1px solid rgb(241 245 249);
  border-radius: 10px;
  background: rgb(248 250 252);
  font-size: 12px;
  line-height: 1.5;
  color: rgb(51 65 85);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.one-sentence-inspiration-chip:hover {
  border-color: rgb(221 214 254);
  background: rgb(250 245 255);
  box-shadow: 0 1px 2px rgb(139 92 246 / 0.08);
}

.one-sentence-generate-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, rgb(124 58 237) 0%, rgb(79 70 229) 100%);
  font-size: 14px;
  font-weight: 500;
  color: white;
  box-shadow: 0 2px 8px rgb(124 58 237 / 0.28);
  cursor: pointer;
  transition:
    opacity 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.one-sentence-generate-btn:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgb(124 58 237 / 0.35);
  transform: translateY(-1px);
}

.one-sentence-generate-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
}
</style>
