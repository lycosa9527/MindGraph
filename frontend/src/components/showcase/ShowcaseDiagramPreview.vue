<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  ChevronLeft,
  ChevronRight,
  Image as ImageIcon,
  Loader2,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
} from '@lucide/vue'

import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { resolveCarouselSlides, type ShowcaseCarouselSlide } from '@/components/showcase/showcaseGallery'
import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import {
  popShowcaseReaderLock,
  pushShowcaseReaderLock,
} from '@/composables/presentation/presentationDiagramEdit'
import { useDiagramStore } from '@/stores'
import type { DiagramType } from '@/types'
import { decodeMgFileToJsonText } from '@/utils/mgInterchange'
import {
  cloneShowcaseDiagramSpec,
  resolveShowcaseDiagramType,
} from '@/utils/showcaseDiagramThumbnail'
import { resolveDevStaticUrl } from '@/utils/devStaticUrl'

pushShowcaseReaderLock()

const props = withDefaults(
  defineProps<{
    postId?: string | null
    thumbnailUrl?: string | null
    sourceFileUrl?: string | null
    specJsonUrl?: string | null
    spec?: unknown
    diagramType?: string | null
    watermarkName?: string | null
    watermarkOrganization?: string | null
    galleryItems?: Array<{
      kind: 'image' | 'diagram'
      url?: string | null
      missing?: boolean
      filename?: string | null
      diagram_id?: string | null
      title?: string | null
      diagram_type?: string | null
      spec?: Record<string, unknown>
    }>
  }>(),
  {
    galleryItems: () => [],
  }
)

const { t } = useLanguage()

const ZOOM_MIN = 0.6
const ZOOM_MAX = 2.5
const ZOOM_STEP = 0.15
const WATERMARK_TILE_COUNT = 9

type PreviewMode = 'idle' | 'loading' | 'diagram' | 'image' | 'empty' | 'error'

const previewMode = ref<PreviewMode>('idle')
const previewError = ref<string | null>(null)
const zoomLevel = ref(1)
const activeGalleryIndex = ref(0)
const carouselRef = ref<HTMLElement | null>(null)
const readerRoot = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)
const failedImageSlideIndexes = ref(new Set<number>())
const slideBlobUrls = ref<Record<number, string>>({})

function resolvedImageSrc(index: number, url: string): string {
  return slideBlobUrls.value[index] ?? url
}

async function prefetchSlideImage(index: number, url: string): Promise<void> {
  if (slideBlobUrls.value[index] || failedImageSlideIndexes.value.has(index)) return
  const resolved = resolveDevStaticUrl(url) ?? url
  try {
    const response = await fetch(resolved, { credentials: 'include', cache: 'no-store' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const blob = await response.blob()
    if (!blob.type.startsWith('image/')) throw new Error('not image')
    slideBlobUrls.value = { ...slideBlobUrls.value, [index]: URL.createObjectURL(blob) }
  } catch {
    const next = new Set(failedImageSlideIndexes.value)
    next.add(index)
    failedImageSlideIndexes.value = next
  }
}

function revokeSlideBlobUrls(): void {
  for (const url of Object.values(slideBlobUrls.value)) {
    URL.revokeObjectURL(url)
  }
  slideBlobUrls.value = {}
}

const carouselSlides = computed((): ShowcaseCarouselSlide[] =>
  resolveCarouselSlides({
    galleryItems: props.galleryItems,
    spec: props.spec,
    postId: props.postId,
    sourceFileUrl: props.sourceFileUrl,
    thumbnailUrl: props.thumbnailUrl,
    resolveUrl: resolveDevStaticUrl,
  })
)

const hasCarousel = computed(() => carouselSlides.value.length > 1)
const isAllImageCarousel = computed(
  () =>
    hasCarousel.value &&
    carouselSlides.value.every((slide) => slide.kind === 'image' && !('missing' in slide && slide.missing))
)

const activeSlide = computed(() => carouselSlides.value[activeGalleryIndex.value] ?? null)

function isRenderableImageSlide(
  slide: ShowcaseCarouselSlide | null,
  index?: number
): slide is { kind: 'image'; url: string; filename?: string } {
  if (!slide || slide.kind !== 'image' || !slide.url || ('missing' in slide && slide.missing)) {
    return false
  }
  if (typeof index === 'number' && failedImageSlideIndexes.value.has(index)) {
    return false
  }
  return true
}

const isActiveImageSlide = computed(() =>
  isRenderableImageSlide(activeSlide.value, activeGalleryIndex.value)
)

const isActiveDiagramSlide = computed(
  () =>
    hasCarousel.value &&
    activeSlide.value?.kind === 'diagram' &&
    previewMode.value === 'diagram'
)

const carouselCounter = computed(() => {
  if (!hasCarousel.value) return ''
  return `${activeGalleryIndex.value + 1} / ${carouselSlides.value.length}`
})

const diagramStore = useDiagramStore()

let diagramBackup: {
  type: DiagramType | null
  spec: Record<string, unknown> | null
} | null = null

const watermarkText = computed(() => {
  const name = props.watermarkName?.trim()
  const org = props.watermarkOrganization?.trim()
  if (name && org) return `${name} · ${org}`
  return name || org || ''
})

const watermarkTiles = computed(() =>
  watermarkText.value ? Array.from({ length: WATERMARK_TILE_COUNT }, (_, i) => i) : []
)

const zoomPercent = computed(() => `${Math.round(zoomLevel.value * 100)}%`)

const contentZoomStyle = computed(() => ({
  transform: `scale(${zoomLevel.value})`,
  transformOrigin: 'top center',
}))

const imagePreviewUrl = computed(() => {
  const slide = carouselSlides.value[0]
  if (slide?.kind === 'image' && slide.url && !('missing' in slide && slide.missing)) return slide.url
  const src = resolveDevStaticUrl(props.sourceFileUrl) ?? ''
  if (/\.(png|jpe?g|webp|gif)(\?|$)/i.test(src)) return src
  return props.thumbnailUrl ?? null
})

const hasToolbar = computed(() => {
  if (hasCarousel.value) {
    return isActiveImageSlide.value || isActiveDiagramSlide.value
  }
  return previewMode.value === 'image' || previewMode.value === 'diagram'
})

const isDiagramCanvasMode = computed(() => previewMode.value === 'diagram')

function syncDiagramZoomFromEvent(payload: { zoom?: number }): void {
  if (typeof payload.zoom === 'number' && Number.isFinite(payload.zoom)) {
    zoomLevel.value = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, payload.zoom))
  }
}

function diagramZoomIn(): void {
  eventBus.emit('view:zoom_in_requested', {})
}

function diagramZoomOut(): void {
  eventBus.emit('view:zoom_out_requested', {})
}

function diagramResetZoom(): void {
  eventBus.emit('view:fit_to_canvas_requested', { animate: false })
}

function isRenderableSpec(spec: unknown): spec is Record<string, unknown> {
  if (!spec || typeof spec !== 'object') return false
  const obj = spec as Record<string, unknown>
  if (obj.source === 'image_upload') return false
  if (obj.source === 'mg_upload' && !obj.topic && !obj.nodes && !obj.children && !obj.center) {
    return false
  }
  return Boolean(obj.topic || obj.nodes || obj.children || obj.center || obj.Whole)
}

function slideDiagramType(slide: ShowcaseCarouselSlide): string | null {
  if (slide.kind !== 'diagram') return props.diagramType ?? null
  return slide.diagram_type ?? props.diagramType ?? null
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}mg_preview=${Date.now()}`, {
    credentials: 'include',
    cache: 'no-store',
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.json()
}

async function resolveDiagramSpecForSlide(slide: ShowcaseCarouselSlide | null): Promise<Record<string, unknown> | null> {
  if (!slide || slide.kind !== 'diagram') {
    if (isRenderableSpec(props.spec)) return props.spec as Record<string, unknown>
    return null
  }
  if (slide.spec && isRenderableSpec(slide.spec)) return slide.spec

  if (isRenderableSpec(props.spec)) return props.spec as Record<string, unknown>

  if (props.specJsonUrl) {
    const fromUrl = await fetchJson(props.specJsonUrl)
    if (isRenderableSpec(fromUrl)) return fromUrl
  }

  const sourceUrl = resolveDevStaticUrl(props.sourceFileUrl)
  if (sourceUrl && /\.mg(\?|$)/i.test(sourceUrl)) {
    const response = await fetch(`${sourceUrl}${sourceUrl.includes('?') ? '&' : '?'}mg_preview=${Date.now()}`, {
      credentials: 'include',
      cache: 'no-store',
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const text = await decodeMgFileToJsonText(await response.arrayBuffer())
    const parsed = JSON.parse(text) as unknown
    if (isRenderableSpec(parsed)) return parsed
  }

  return null
}

function backupDiagramStore(): void {
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

async function loadPreview(): Promise<void> {
  if (hasCarousel.value && isAllImageCarousel.value) {
    previewMode.value = 'image'
    previewError.value = null
    return
  }

  if (activeSlide.value?.kind === 'image') {
    previewError.value = null
    if (isRenderableImageSlide(activeSlide.value, activeGalleryIndex.value)) {
      previewMode.value = 'image'
      return
    }
    previewMode.value = 'empty'
    return
  }

  const token = ++previewLoadToken
  previewError.value = null
  previewMode.value = 'loading'

  try {
    const spec = await resolveDiagramSpecForSlide(activeSlide.value)
    if (token !== previewLoadToken) return
    if (spec) {
      if (!diagramBackup) backupDiagramStore()
      const specClone = cloneShowcaseDiagramSpec(spec)
      const diagramType = resolveShowcaseDiagramType(specClone, slideDiagramType(activeSlide.value!))
      const loaded = diagramStore.loadFromSpec(specClone, diagramType, { emitLoaded: false })
      if (!loaded) throw new Error('Failed to load diagram spec')
      previewMode.value = 'diagram'
      return
    }

    if (imagePreviewUrl.value) {
      previewMode.value = 'image'
      return
    }

    previewMode.value = 'empty'
  } catch {
    if (token !== previewLoadToken) return
    if (imagePreviewUrl.value) {
      previewMode.value = 'image'
      return
    }
    previewMode.value = 'error'
    previewError.value = String(t('showcase.detail.diagramPreviewFailed'))
  }
}

function syncCarouselIndex(): void {
  const el = carouselRef.value
  if (!el || carouselSlides.value.length < 2) return
  const width = el.clientWidth
  if (width < 1) return
  const index = Math.max(0, Math.min(carouselSlides.value.length - 1, Math.round(el.scrollLeft / width)))
  if (index !== activeGalleryIndex.value) {
    activeGalleryIndex.value = index
  }
}

function scrollToSlide(index: number): void {
  const el = carouselRef.value
  if (!el) return
  const clamped = Math.max(0, Math.min(carouselSlides.value.length - 1, index))
  activeGalleryIndex.value = clamped
  el.scrollTo({ left: clamped * el.clientWidth, behavior: 'smooth' })
}

function goPrevSlide(): void {
  scrollToSlide(activeGalleryIndex.value - 1)
}

function goNextSlide(): void {
  scrollToSlide(activeGalleryIndex.value + 1)
}

function zoomIn() {
  zoomLevel.value = Math.min(ZOOM_MAX, Math.round((zoomLevel.value + ZOOM_STEP) * 100) / 100)
}

function zoomOut() {
  zoomLevel.value = Math.max(ZOOM_MIN, Math.round((zoomLevel.value - ZOOM_STEP) * 100) / 100)
}

function resetZoom() {
  zoomLevel.value = 1
}

function onGalleryImageError(index: number): void {
  failedImageSlideIndexes.value.add(index)
}

function isFailedImageSlide(slide: ShowcaseCarouselSlide, index: number): boolean {
  return slide.kind === 'image' && failedImageSlideIndexes.value.has(index)
}

function missingImageSlideLabel(slide: ShowcaseCarouselSlide): string {
  if (slide.kind === 'image' && slide.filename) return slide.filename
  return String(t('showcase.detail.galleryImage'))
}

function diagramSlideLabel(slide: ShowcaseCarouselSlide): string {
  if (slide.kind === 'diagram' && slide.title) return slide.title
  return String(t('showcase.detail.galleryDiagram'))
}

function syncFullscreenState() {
  isFullscreen.value = document.fullscreenElement === readerRoot.value
}

async function toggleFullscreen() {
  if (!readerRoot.value) return
  try {
    if (!document.fullscreenElement) {
      await readerRoot.value.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch {
    /* browser may block fullscreen */
  }
}

function blockCopyEvent(event: Event) {
  event.preventDefault()
}

function blockReaderKeydown(event: KeyboardEvent) {
  const key = event.key
  if (previewMode.value === 'diagram' && (key === 'Delete' || key === 'Backspace')) {
    event.preventDefault()
    event.stopPropagation()
    return
  }
  if (previewMode.value === 'diagram') return
  const normalized = key.toLowerCase()
  const mod = event.ctrlKey || event.metaKey
  if (mod && (normalized === 'c' || normalized === 'a' || normalized === 'x' || normalized === 's' || normalized === 'p')) {
    event.preventDefault()
  }
}

const singlePreviewSourceKey = computed(() =>
  [
    props.thumbnailUrl ?? '',
    props.sourceFileUrl ?? '',
    props.specJsonUrl ?? '',
    props.diagramType ?? '',
    isRenderableSpec(props.spec) ? 'spec' : '',
    carouselSlides.value.map((slide) => (slide.kind === 'image' ? slide.url : slide.title)).join('|'),
  ].join('\u0001')
)

let previewLoadToken = 0

watch(
  singlePreviewSourceKey,
  () => {
    activeGalleryIndex.value = 0
    if (carouselRef.value) {
      carouselRef.value.scrollLeft = 0
    }
    zoomLevel.value = 1
    if (!hasCarousel.value) {
      void loadPreview()
    }
  },
  { immediate: true }
)

watch(
  () => [hasCarousel.value, activeGalleryIndex.value, isAllImageCarousel.value] as const,
  ([carousel, , allImages]) => {
    if (!carousel) return
    zoomLevel.value = 1
    if (allImages) {
      previewMode.value = 'image'
      return
    }
    void loadPreview()
  }
)

watch(
  () => carouselSlides.value.length,
  () => {
    failedImageSlideIndexes.value = new Set()
    revokeSlideBlobUrls()
  }
)

watch(
  () =>
    carouselSlides.value
      .map((slide, index) =>
        slide.kind === 'image' && slide.url && !('missing' in slide && slide.missing)
          ? `${index}:${slide.url}`
          : ''
      )
      .join('|'),
  () => {
    failedImageSlideIndexes.value = new Set()
    revokeSlideBlobUrls()
    carouselSlides.value.forEach((slide, index) => {
      if (slide.kind === 'image' && slide.url && !('missing' in slide && slide.missing)) {
        void prefetchSlideImage(index, slide.url)
      }
    })
  },
  { immediate: true }
)

watch(
  () => imagePreviewUrl.value,
  (url) => {
    if (hasCarousel.value || !url) return
    failedImageSlideIndexes.value = new Set()
    revokeSlideBlobUrls()
    void prefetchSlideImage(0, url)
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('fullscreenchange', syncFullscreenState)
  eventBus.on('view:zoom_changed', syncDiagramZoomFromEvent)
})

onBeforeUnmount(() => {
  popShowcaseReaderLock()
  revokeSlideBlobUrls()
  document.removeEventListener('fullscreenchange', syncFullscreenState)
  eventBus.off('view:zoom_changed', syncDiagramZoomFromEvent)
  restoreDiagramStore()
  if (document.fullscreenElement === readerRoot.value) {
    void document.exitFullscreen()
  }
})
</script>

<template>
  <div
    ref="readerRoot"
    class="showcase-diagram-reader flex h-full min-h-0 flex-col bg-white"
    :class="{ 'showcase-diagram-reader--fullscreen': isFullscreen }"
  >
    <div
      v-if="hasToolbar"
      class="flex shrink-0 items-center justify-end gap-1 border-b border-gray-100 px-3 py-1.5"
    >
      <template v-if="previewMode === 'image' || isActiveImageSlide">
        <button
          type="button"
          class="diagram-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-40"
          :disabled="zoomLevel <= ZOOM_MIN"
          :title="String(t('showcase.detail.zoomOut'))"
          @click="zoomOut"
        >
          <ZoomOut class="h-3.5 w-3.5" />
        </button>
        <span class="min-w-[2.75rem] text-center text-xs tabular-nums text-gray-500">{{ zoomPercent }}</span>
        <button
          type="button"
          class="diagram-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-40"
          :disabled="zoomLevel >= ZOOM_MAX"
          :title="String(t('showcase.detail.zoomIn'))"
          @click="zoomIn"
        >
          <ZoomIn class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="diagram-reader-toolbar-btn rounded-lg px-2 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-800"
          @click="resetZoom"
        >
          {{ t('showcase.detail.zoomReset') }}
        </button>
        <span class="mx-1 h-4 w-px bg-gray-200" />
      </template>
      <template v-else-if="isDiagramCanvasMode || isActiveDiagramSlide">
        <button
          type="button"
          class="diagram-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800"
          :title="String(t('showcase.detail.zoomOut'))"
          @click="diagramZoomOut"
        >
          <ZoomOut class="h-3.5 w-3.5" />
        </button>
        <span class="min-w-[2.75rem] text-center text-xs tabular-nums text-gray-500">{{ zoomPercent }}</span>
        <button
          type="button"
          class="diagram-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800"
          :title="String(t('showcase.detail.zoomIn'))"
          @click="diagramZoomIn"
        >
          <ZoomIn class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="diagram-reader-toolbar-btn rounded-lg px-2 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-800"
          @click="diagramResetZoom"
        >
          {{ t('showcase.detail.zoomReset') }}
        </button>
        <span class="mx-1 h-4 w-px bg-gray-200" />
      </template>
      <button
        type="button"
        class="diagram-reader-toolbar-btn inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-800"
        @click="toggleFullscreen"
      >
        <Minimize2 v-if="isFullscreen" class="h-3.5 w-3.5" />
        <Maximize2 v-else class="h-3.5 w-3.5" />
        {{
          isFullscreen
            ? t('showcase.detail.exitFullscreen')
            : t('showcase.detail.enterFullscreen')
        }}
      </button>
    </div>

    <div
      class="relative min-h-0 flex-1 bg-white"
      :class="
        hasCarousel || previewMode === 'image' ? 'overflow-hidden' : 'overflow-hidden'
      "
      @keydown.capture="blockReaderKeydown"
    >
      <!-- Xiaohongshu-style multi-image carousel -->
      <div
        v-if="hasCarousel"
        class="relative flex h-full min-h-[40vh] flex-col"
      >
        <div
          class="pointer-events-none absolute right-3 top-3 z-30 rounded-full bg-black/55 px-2.5 py-0.5 text-xs font-medium tabular-nums text-white"
        >
          {{ carouselCounter }}
        </div>

        <button
          v-if="activeGalleryIndex > 0"
          type="button"
          class="showcase-gallery-nav showcase-gallery-nav--prev"
          :aria-label="String(t('showcase.detail.galleryPrev'))"
          @click="goPrevSlide"
        >
          <ChevronLeft class="h-5 w-5" />
        </button>
        <button
          v-if="activeGalleryIndex < carouselSlides.length - 1"
          type="button"
          class="showcase-gallery-nav showcase-gallery-nav--next"
          :aria-label="String(t('showcase.detail.galleryNext'))"
          @click="goNextSlide"
        >
          <ChevronRight class="h-5 w-5" />
        </button>

        <div
          ref="carouselRef"
          class="showcase-gallery-carousel min-h-0 flex-1"
          @scroll.passive="syncCarouselIndex"
        >
          <div
            v-for="(slide, index) in carouselSlides"
            :key="`${slide.kind}-${index}`"
            class="showcase-gallery-slide"
          >
            <template v-if="isRenderableImageSlide(slide, index)">
              <div
                class="showcase-watermark-host relative flex h-full w-full items-center justify-center overflow-auto px-4 py-6"
                :style="index === activeGalleryIndex ? contentZoomStyle : undefined"
                @copy="blockCopyEvent"
                @cut="blockCopyEvent"
                @selectstart="blockCopyEvent"
                @contextmenu="blockCopyEvent"
                @dragstart="blockCopyEvent"
              >
                <div
                  v-if="watermarkText"
                  class="showcase-page-watermark"
                  aria-hidden="true"
                >
                  <span v-for="tile in watermarkTiles" :key="tile">{{ watermarkText }}</span>
                </div>
                <img
                  :src="resolvedImageSrc(index, slide.url)"
                  :alt="slide.filename ?? ''"
                  class="max-h-full max-w-full object-contain"
                  draggable="false"
                  loading="lazy"
                  @error="onGalleryImageError(index)"
                />
              </div>
            </template>

            <template v-else-if="(slide.kind === 'image' && slide.missing) || isFailedImageSlide(slide, index)">
              <div
                class="flex h-full min-h-[40vh] flex-col items-center justify-center gap-2 px-6 text-center text-gray-400"
              >
                <ImageIcon class="h-10 w-10 text-gray-300" />
                <p class="text-sm font-medium text-gray-600">
                  {{ missingImageSlideLabel(slide) }}
                </p>
                <p class="text-xs">{{ t('showcase.detail.galleryImageMissing') }}</p>
              </div>
            </template>

            <template v-else>
              <div
                v-if="index === activeGalleryIndex && previewMode === 'diagram'"
                class="relative h-full min-h-[50vh]"
              >
                <div
                  v-if="watermarkText"
                  class="showcase-diagram-watermark pointer-events-none absolute inset-0 z-20 grid grid-cols-3 gap-10 overflow-hidden p-6"
                  aria-hidden="true"
                >
                  <span
                    v-for="tile in watermarkTiles"
                    :key="tile"
                    class="showcase-diagram-watermark-tile"
                  >
                    {{ watermarkText }}
                  </span>
                </div>
                <DiagramCanvas
                  :show-minimap="false"
                  :fit-view-on-init="true"
                  :hand-tool-active="true"
                  :presentation-hand-pan-mode="true"
                />
              </div>
              <div
                v-else-if="index === activeGalleryIndex && previewMode === 'loading'"
                class="flex h-full min-h-[40vh] items-center justify-center text-gray-500"
              >
                <Loader2 class="mr-2 h-5 w-5 animate-spin" />
                <span class="text-sm">{{ t('showcase.detail.diagramPreviewLoading') }}</span>
              </div>
              <div
                v-else
                class="flex h-full min-h-[40vh] flex-col items-center justify-center gap-2 px-6 text-center text-gray-400"
              >
                <ImageIcon class="h-10 w-10 text-gray-300" />
                <p class="text-sm font-medium text-gray-600">
                  {{ diagramSlideLabel(slide) }}
                </p>
                <p class="text-xs">{{ t('showcase.detail.gallerySwipeHint') }}</p>
              </div>
            </template>
          </div>
        </div>

        <div class="showcase-gallery-dots shrink-0">
          <button
            v-for="(_, index) in carouselSlides"
            :key="index"
            type="button"
            class="showcase-gallery-dot"
            :class="{ 'is-active': index === activeGalleryIndex }"
            :aria-label="`${index + 1} / ${carouselSlides.length}`"
            @click="scrollToSlide(index)"
          />
        </div>
      </div>

      <!-- Single asset preview -->
      <template v-else>
        <div
          v-if="previewMode === 'loading'"
          class="flex h-full min-h-[40vh] items-center justify-center text-gray-500"
        >
          <Loader2 class="mr-2 h-5 w-5 animate-spin" />
          <span class="text-sm">{{ t('showcase.detail.diagramPreviewLoading') }}</span>
        </div>

        <div v-else-if="previewMode === 'diagram'" class="relative h-full min-h-[50vh]">
          <div
            v-if="watermarkText"
            class="showcase-diagram-watermark pointer-events-none absolute inset-0 z-20 grid grid-cols-3 gap-10 overflow-hidden p-6"
            aria-hidden="true"
          >
            <span v-for="tile in watermarkTiles" :key="tile" class="showcase-diagram-watermark-tile">
              {{ watermarkText }}
            </span>
          </div>
          <DiagramCanvas
            :show-minimap="false"
            :fit-view-on-init="true"
            :hand-tool-active="true"
            :presentation-hand-pan-mode="true"
          />
        </div>

        <div
          v-else-if="previewMode === 'image' && imagePreviewUrl"
          class="showcase-watermark-host relative flex min-h-full justify-center overflow-auto px-4 py-6"
          :style="contentZoomStyle"
          @copy="blockCopyEvent"
          @cut="blockCopyEvent"
          @selectstart="blockCopyEvent"
          @contextmenu="blockCopyEvent"
          @dragstart="blockCopyEvent"
        >
          <div
            v-if="watermarkText"
            class="showcase-page-watermark"
            aria-hidden="true"
          >
            <span v-for="tile in watermarkTiles" :key="tile">{{ watermarkText }}</span>
          </div>
          <img
            :src="imagePreviewUrl ? resolvedImageSrc(0, imagePreviewUrl) : ''"
            alt=""
            class="max-h-full max-w-full object-contain"
            draggable="false"
          />
        </div>

        <div
          v-else-if="previewMode === 'error'"
          class="flex min-h-[50vh] flex-col items-center justify-center px-6 text-center text-gray-400"
        >
          <ImageIcon class="mb-3 h-12 w-12 text-gray-300" />
          <p class="text-sm">{{ previewError }}</p>
        </div>

        <div
          v-else
          class="flex min-h-[50vh] flex-col items-center justify-center px-6 text-center text-gray-400"
        >
          <ImageIcon class="mb-3 h-12 w-12 text-gray-300" />
          <p class="text-sm">{{ t('showcase.detail.noDiagramPreview') }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.diagram-reader-toolbar-btn {
  border: none;
  outline: none;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.diagram-reader-toolbar-btn:focus,
.diagram-reader-toolbar-btn:focus-visible {
  outline: none;
}

.showcase-gallery-carousel {
  display: flex;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  scrollbar-width: none;
  -ms-overflow-style: none;
  touch-action: pan-x;
}

.showcase-gallery-carousel::-webkit-scrollbar {
  display: none;
}

.showcase-gallery-slide {
  flex: 0 0 100%;
  width: 100%;
  scroll-snap-align: start;
  scroll-snap-stop: always;
  min-height: 100%;
}

.showcase-gallery-nav {
  position: absolute;
  top: 50%;
  z-index: 25;
  display: flex;
  height: 2rem;
  width: 2rem;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 9999px;
  background: rgb(0 0 0 / 0.35);
  color: #fff;
  transform: translateY(-50%);
  cursor: pointer;
  transition: background 0.15s ease;
}

.showcase-gallery-nav:hover {
  background: rgb(0 0 0 / 0.5);
}

.showcase-gallery-nav--prev {
  left: 0.5rem;
}

.showcase-gallery-nav--next {
  right: 0.5rem;
}

.showcase-gallery-dots {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  padding: 0.625rem 0 0.75rem;
}

.showcase-gallery-dot {
  height: 0.375rem;
  width: 0.375rem;
  border: none;
  border-radius: 9999px;
  background: #d6d3d1;
  padding: 0;
  cursor: pointer;
  transition:
    width 0.2s ease,
    background 0.2s ease;
}

.showcase-gallery-dot.is-active {
  width: 1.125rem;
  background: #1c1917;
}

.showcase-diagram-watermark-tile {
  transform: rotate(-22deg);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
  color: #6b7280;
  text-align: center;
  white-space: nowrap;
  opacity: 0.14;
  user-select: none;
}

:deep(.showcase-watermark-host) {
  position: relative;
}

:deep(.showcase-page-watermark) {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 2.5rem 1rem;
  padding: 2rem 0.75rem;
  overflow: hidden;
  pointer-events: none;
  user-select: none;
}

:deep(.showcase-page-watermark span) {
  transform: rotate(-22deg);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
  color: #6b7280;
  text-align: center;
  white-space: nowrap;
  opacity: 0.14;
}

.showcase-diagram-reader:fullscreen {
  width: 100%;
  height: 100%;
  background: #fff;
}

.showcase-diagram-reader:fullscreen .relative.min-h-0 {
  height: 100%;
}

.showcase-diagram-reader :deep(.diagram-canvas) {
  height: 100%;
  min-height: 0;
}

.showcase-diagram-reader :deep(.diagram-canvas--hand-tool),
.showcase-diagram-reader :deep(.diagram-canvas--hand-tool .vue-flow__pane) {
  cursor: grab;
}

.showcase-diagram-reader :deep(.diagram-canvas--hand-tool .vue-flow__pane:active) {
  cursor: grabbing;
}
</style>
