<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Loader2 } from '@lucide/vue'

import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import DiagramSessionProvider from '@/components/diagram/DiagramSessionProvider.vue'
import { useLanguage } from '@/composables'
import {
  cloneShowcaseDiagramSpec,
  fetchDiagramSpecPngBlob,
  resolveShowcaseDiagramType,
} from '@/utils/showcaseDiagramThumbnail'

const props = defineProps<{
  spec: Record<string, unknown> | null
  diagramType?: string | null
  thumbnailUrl?: string | null
  emptyLabelKey?: string
}>()

const { t } = useLanguage()

const isReady = ref(false)
const hasError = ref(false)
const canvasMounted = ref(false)
let loadToken = 0

const emptyLabel = computed(() =>
  String(t(props.emptyLabelKey ?? 'showcase.publishModal.templatePreviewEmpty'))
)

const showThumbnailPlaceholder = computed(
  () => Boolean(props.thumbnailUrl) && !isReady.value && !hasError.value
)

const previewSpec = computed(() => {
  if (!props.spec) return null
  return cloneShowcaseDiagramSpec(props.spec)
})

const previewDiagramType = computed(() => {
  if (!previewSpec.value) return null
  return resolveShowcaseDiagramType(previewSpec.value, props.diagramType)
})

const previewSessionKey = computed(() => {
  if (!previewSpec.value || !previewDiagramType.value) return 'empty'
  return `${previewDiagramType.value}:${JSON.stringify(previewSpec.value).length}`
})

watch(
  () => [props.spec, props.diagramType] as const,
  ([spec]) => {
    const token = ++loadToken
    if (!spec) {
      isReady.value = false
      hasError.value = false
      canvasMounted.value = false
      return
    }
    isReady.value = false
    hasError.value = false
    canvasMounted.value = true
    // Allow VueFlow to mount under the isolated session, then mark ready.
    requestAnimationFrame(() => {
      if (token !== loadToken) return
      isReady.value = true
    })
  },
  { immediate: true }
)

async function captureThumbnail(): Promise<Blob | null> {
  if (!previewSpec.value || !previewDiagramType.value) return null
  return fetchDiagramSpecPngBlob(previewSpec.value, previewDiagramType.value)
}

defineExpose({ captureThumbnail })
</script>

<template>
  <div class="showcase-inline-diagram-preview flex h-full min-h-0 flex-col bg-gray-50">
    <div
      v-if="!spec"
      class="flex flex-1 flex-col items-center justify-center px-6 text-center text-gray-400"
    >
      <p class="text-sm">{{ emptyLabel }}</p>
    </div>
    <div
      v-else
      class="relative min-h-0 flex-1"
    >
      <img
        v-if="showThumbnailPlaceholder && thumbnailUrl"
        :src="thumbnailUrl"
        alt=""
        class="absolute inset-0 z-0 h-full w-full object-contain p-4"
      />
      <DiagramSessionProvider
        v-if="canvasMounted && previewSpec && previewDiagramType"
        :key="previewSessionKey"
        mode="readonly"
        :spec="previewSpec"
        :diagram-type="previewDiagramType"
      >
        <DiagramCanvas
          class="relative z-1"
          :show-minimap="false"
          :fit-view-on-init="true"
          :hand-tool-active="true"
          :presentation-hand-pan-mode="true"
        />
      </DiagramSessionProvider>
      <div
        v-if="!isReady && !hasError"
        class="absolute inset-0 z-10 flex items-center justify-center bg-gray-50/80 text-gray-500"
      >
        <Loader2 class="mr-2 h-5 w-5 animate-spin" />
        <span class="text-sm">{{ t('showcase.detail.diagramPreviewLoading') }}</span>
      </div>
      <div
        v-else-if="hasError"
        class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 px-6 text-center text-gray-400"
      >
        <img
          v-if="thumbnailUrl"
          :src="thumbnailUrl"
          alt=""
          class="max-h-[55%] max-w-full object-contain opacity-90"
        />
        <p class="text-sm">{{ t('showcase.detail.diagramPreviewFailed') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.showcase-inline-diagram-preview :deep(.diagram-canvas) {
  height: 100%;
  min-height: 360px;
}

.showcase-inline-diagram-preview :deep(.diagram-canvas--hand-tool),
.showcase-inline-diagram-preview :deep(.diagram-canvas--hand-tool .vue-flow__pane) {
  cursor: grab;
}

.showcase-inline-diagram-preview :deep(.diagram-canvas--hand-tool .vue-flow__pane:active) {
  cursor: grabbing;
}
</style>
