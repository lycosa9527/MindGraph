<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Loader2 } from '@lucide/vue'

import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import {
  popCaseSquareReaderLock,
  pushCaseSquareReaderLock,
} from '@/composables/presentation/presentationDiagramEdit'
import { useDiagramStore } from '@/stores'
import type { DiagramType } from '@/types'
import { dataUrlToPngBlob } from '@/components/caseSquare/caseSquareShared'
import {
  cloneCaseSquareDiagramSpec,
  resolveCaseSquareDiagramType,
} from '@/utils/caseSquareDiagramThumbnail'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

pushCaseSquareReaderLock()

const props = defineProps<{
  spec: Record<string, unknown> | null
  diagramType?: string | null
  thumbnailUrl?: string | null
  emptyLabelKey?: string
}>()

const { t } = useLanguage()
const diagramStore = useDiagramStore()

const isReady = ref(false)
const hasError = ref(false)
const canvasMounted = ref(false)
const previewRoot = ref<HTMLElement | null>(null)
let loadToken = 0

let diagramBackup: {
  type: DiagramType | null
  spec: Record<string, unknown> | null
} | null = null

const emptyLabel = computed(() =>
  String(t(props.emptyLabelKey ?? 'caseSquare.publishModal.templatePreviewEmpty'))
)

const showThumbnailPlaceholder = computed(
  () => Boolean(props.thumbnailUrl) && !isReady.value && !hasError.value
)

function backupDiagramStore(): void {
  if (diagramBackup) return
  diagramBackup = {
    type: diagramStore.type,
    spec: diagramStore.getSpecForSave() as Record<string, unknown> | null,
  }
}

function restoreDiagramStore(): void {
  const backup = diagramBackup
  diagramBackup = null
  if (!backup?.type || !backup.spec) return
  diagramStore.loadFromSpec(backup.spec, backup.type, { emitLoaded: false })
}

function waitForViewFitCompleted(timeoutMs = 4_000): Promise<void> {
  return new Promise((resolve, reject) => {
    let off: (() => void) | null = null
    const timer = window.setTimeout(() => {
      off?.()
      reject(new Error('fit timeout'))
    }, timeoutMs)
    off = eventBus.once('view:fit_completed', () => {
      window.clearTimeout(timer)
      resolve()
    })
  })
}

async function loadSpecIntoCanvas(spec: Record<string, unknown>, diagramTypeValue: string): Promise<void> {
  const token = ++loadToken
  isReady.value = false
  hasError.value = false
  canvasMounted.value = false

  try {
    backupDiagramStore()
    const specClone = cloneCaseSquareDiagramSpec(spec)
    const diagramTypeToLoad = resolveCaseSquareDiagramType(specClone, diagramTypeValue)
    const loaded = diagramStore.loadFromSpec(specClone, diagramTypeToLoad, { emitLoaded: false })
    if (!loaded || token !== loadToken) {
      hasError.value = true
      return
    }

    canvasMounted.value = true
    await nextTick()
    await waitForNextPaint()
    if (token !== loadToken) return
    isReady.value = true
  } catch {
    if (token === loadToken) {
      hasError.value = true
    }
  }
}

watch(
  () => [props.spec, props.diagramType] as const,
  ([spec, diagramTypeValue]) => {
    if (!spec) {
      isReady.value = false
      hasError.value = false
      canvasMounted.value = false
      return
    }
    void loadSpecIntoCanvas(spec, diagramTypeValue ?? '')
  },
  { immediate: true }
)

async function captureThumbnail(): Promise<Blob | null> {
  if (!canvasMounted.value || !previewRoot.value) return null
  try {
    await nextTick()
    eventBus.emit('view:fit_to_canvas_requested', { animate: false, forExport: true })
    try {
      await waitForViewFitCompleted()
    } catch {
      // Continue with best-effort capture.
    }
    await waitForNextPaint()
    const htmlToImage = await import('html-to-image')
    const captureTarget =
      (previewRoot.value.querySelector('.diagram-canvas') as HTMLElement | null) ??
      previewRoot.value
    const dataUrl = await htmlToImage.toPng(captureTarget, { pixelRatio: 2, cacheBust: true })
    const blob = await dataUrlToPngBlob(dataUrl)
    return blob
  } catch {
    return null
  }
}

defineExpose({ captureThumbnail })

onBeforeUnmount(() => {
  popCaseSquareReaderLock()
  restoreDiagramStore()
})
</script>

<template>
  <div class="case-square-inline-diagram-preview flex h-full min-h-0 flex-col bg-gray-50">
    <div v-if="!spec" class="flex flex-1 flex-col items-center justify-center px-6 text-center text-gray-400">
      <p class="text-sm">{{ emptyLabel }}</p>
    </div>
    <div v-else ref="previewRoot" class="relative min-h-0 flex-1">
      <img
        v-if="showThumbnailPlaceholder && thumbnailUrl"
        :src="thumbnailUrl"
        alt=""
        class="absolute inset-0 z-0 h-full w-full object-contain p-4"
      />
      <DiagramCanvas
        v-if="canvasMounted"
        class="relative z-[1]"
        :show-minimap="false"
        :fit-view-on-init="true"
        :hand-tool-active="true"
        :presentation-hand-pan-mode="true"
      />
      <div
        v-if="!isReady && !hasError"
        class="absolute inset-0 z-10 flex items-center justify-center bg-gray-50/80 text-gray-500"
      >
        <Loader2 class="mr-2 h-5 w-5 animate-spin" />
        <span class="text-sm">{{ t('caseSquare.detail.diagramPreviewLoading') }}</span>
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
        <p class="text-sm">{{ t('caseSquare.detail.diagramPreviewFailed') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.case-square-inline-diagram-preview :deep(.diagram-canvas) {
  height: 100%;
  min-height: 360px;
}

.case-square-inline-diagram-preview :deep(.diagram-canvas--hand-tool),
.case-square-inline-diagram-preview :deep(.diagram-canvas--hand-tool .vue-flow__pane) {
  cursor: grab;
}

.case-square-inline-diagram-preview :deep(.diagram-canvas--hand-tool .vue-flow__pane:active) {
  cursor: grabbing;
}
</style>
