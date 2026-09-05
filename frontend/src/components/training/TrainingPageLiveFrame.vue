<script setup lang="ts">
import { computed } from 'vue'

import TrainingCanvasPreview from '@/components/training/TrainingCanvasPreview.vue'
import { useLanguage } from '@/composables'
import { provideTrainingInlineHost } from '@/composables/training/trainingInlineHost'
import { trainingLivePage } from '@/config/trainingPageLive'
import type { MindMapCanvasMode } from '@/stores/ui'

provideTrainingInlineHost()

const props = defineProps<{
  pageKey?: string | null
  diagramType?: string | null
  canvasMode?: MindMapCanvasMode | null
  interactive?: boolean
}>()

const { t } = useLanguage()
const livePage = computed(() => trainingLivePage(props.pageKey))
const isCanvas = computed(() => props.pageKey === 'canvas')
</script>

<template>
  <div
    class="live-frame"
    :class="{ 'live-frame--interactive': interactive }"
  >
    <TrainingCanvasPreview
      v-if="isCanvas"
      :diagram-type="diagramType"
      :canvas-mode="canvasMode"
      :interactive="interactive"
    />
    <div
      v-else
      class="live-frame__world live-frame__world--full"
    >
      <Suspense v-if="livePage">
        <component :is="livePage" />
        <template #fallback>
          <div class="live-frame__loading">
            {{ t('common.loading') }}
          </div>
        </template>
      </Suspense>
    </div>
  </div>
</template>

<style scoped>
.live-frame {
  position: relative;
  height: 100%;
  min-height: 8rem;
  overflow: hidden;
  background: #f8fafc;
  pointer-events: none;
  user-select: none;
}
.live-frame--interactive {
  pointer-events: auto;
  user-select: auto;
}
.live-frame__world--full {
  position: absolute;
  inset: 0;
  overflow: auto;
  pointer-events: auto;
  user-select: auto;
}
.live-frame__world--full > :deep(*) {
  height: auto;
  min-height: 100%;
}
.live-frame__loading {
  display: grid;
  height: 100%;
  place-items: center;
  color: #78716c;
  font-size: 0.85rem;
}
</style>
