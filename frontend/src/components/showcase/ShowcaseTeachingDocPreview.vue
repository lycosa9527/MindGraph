<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { FileText, Loader2, Maximize2, Minimize2, ZoomIn, ZoomOut } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { renderPdfPreview } from '@/utils/renderPdfPreview'

type FileKind = 'pdf' | 'docx' | 'doc' | 'pptx' | 'unknown'

function attachmentFileKind(url: string | null | undefined): FileKind {
  if (!url) return 'unknown'
  try {
    const path = new URL(url, 'http://local').pathname.toLowerCase()
    if (path.endsWith('.pdf')) return 'pdf'
    if (path.endsWith('.pptx')) return 'pptx'
    if (path.endsWith('.docx')) return 'docx'
    if (path.endsWith('.doc')) return 'doc'
  } catch {
    const lower = url.toLowerCase().split('?')[0] ?? ''
    if (lower.endsWith('.pdf')) return 'pdf'
    if (lower.endsWith('.pptx')) return 'pptx'
    if (lower.endsWith('.docx')) return 'docx'
    if (lower.endsWith('.doc')) return 'doc'
  }
  return 'unknown'
}

const props = defineProps<{
  attachmentUrl?: string | null
  /** LibreOffice-converted PDF for Office docs (PPTX/DOCX/DOC) inline preview. */
  previewUrl?: string | null
  /** Post id — used to stop pending on showcase:cover_fail. */
  postId?: string | null
  fallbackText?: string
  watermarkName?: string | null
  watermarkOrganization?: string | null
}>()

const { t } = useLanguage()

const WATERMARK_TILE_COUNT = 36
const PDF_BASE_SCALE = 1.5
const ZOOM_MIN = 0.5
const ZOOM_MAX = 2.5
const ZOOM_STEP = 0.15
/** Align with backend COVER_SSE_MAX_SECONDS — fail UI if SSE never delivers. */
const OFFICE_PENDING_TIMEOUT_MS = 210_000

const fileKind = computed<FileKind>(() => attachmentFileKind(props.attachmentUrl))

const isOfficeKind = computed(
  () =>
    fileKind.value === 'docx' || fileKind.value === 'doc' || fileKind.value === 'pptx'
)

const absoluteAttachmentUrl = computed(() => {
  if (!props.attachmentUrl || typeof window === 'undefined') return null
  return new URL(props.attachmentUrl, window.location.origin).href
})

const absolutePreviewUrl = computed(() => {
  if (!props.previewUrl || typeof window === 'undefined') return null
  return new URL(props.previewUrl, window.location.origin).href
})

/** True after SSE cover_fail while preview.pdf is still missing. */
const previewConversionFailed = ref(false)
let officePendingTimer: ReturnType<typeof setTimeout> | null = null

function clearOfficePendingTimer(): void {
  if (officePendingTimer != null) {
    clearTimeout(officePendingTimer)
    officePendingTimer = null
  }
}

watch(
  () => props.previewUrl,
  (url) => {
    if (url) previewConversionFailed.value = false
  }
)

watch(
  () => props.postId,
  () => {
    previewConversionFailed.value = false
    clearOfficePendingTimer()
  }
)

/**
 * PDF bytes for pdf.js: native PDF attachment, or LO preview for Office.
 */
const pdfSourceUrl = computed(() => {
  if (fileKind.value === 'pdf') return absoluteAttachmentUrl.value
  if (isOfficeKind.value) return absolutePreviewUrl.value
  return null
})

/** Office + PDF always use the pdf.js reader (pending / fail / ready). */
const showPdfReader = computed(
  () => fileKind.value === 'pdf' || isOfficeKind.value
)

const officePreviewPending = computed(
  () =>
    isOfficeKind.value &&
    !absolutePreviewUrl.value &&
    !previewConversionFailed.value
)

const watermarkText = computed(() => {
  const name = props.watermarkName?.trim()
  const org = props.watermarkOrganization?.trim()
  if (name && org) return `${name} · ${org}`
  return name || org || ''
})

const watermarkTiles = computed(() =>
  watermarkText.value ? Array.from({ length: WATERMARK_TILE_COUNT }, (_, i) => i) : []
)

const hasAttachmentPreview = computed(
  () => fileKind.value === 'pdf' || isOfficeKind.value
)

const hasReaderContent = computed(
  () => hasAttachmentPreview.value || Boolean(props.fallbackText?.trim())
)

/** Fit-to-width baseline (≤1). User zoom multiplies on top. */
const fitZoom = ref(1)
const userZoom = ref(1)

const zoomLevel = computed(() => {
  const raw = fitZoom.value * userZoom.value
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(raw * 100) / 100))
})

const zoomPercent = computed(() => `${Math.round(zoomLevel.value * 100)}%`)

/**
 * Fit-to-width via CSS zoom only. User zoom re-rasters pdf.js (keeps text sharp).
 */
const fitZoomStyle = computed(() => ({
  zoom: fitZoom.value,
}))

/** Fallback text reader still uses combined zoom. */
const contentZoomStyle = computed(() => ({
  zoom: zoomLevel.value,
}))

function zoomIn() {
  userZoom.value = Math.min(
    ZOOM_MAX / Math.max(fitZoom.value, 0.01),
    Math.round((userZoom.value + ZOOM_STEP) * 100) / 100
  )
}

function zoomOut() {
  userZoom.value = Math.max(
    ZOOM_MIN / Math.max(fitZoom.value, 0.01),
    Math.round((userZoom.value - ZOOM_STEP) * 100) / 100
  )
}

function resetZoom() {
  userZoom.value = 1
  void nextTick(() => {
    recomputeFitZoom()
  })
}

const readerRoot = ref<HTMLElement | null>(null)
const viewportEl = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)

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

function blockCopyKeydown(event: KeyboardEvent) {
  const key = event.key.toLowerCase()
  const mod = event.ctrlKey || event.metaKey
  if (mod && (key === 'c' || key === 'a' || key === 'x' || key === 's' || key === 'p')) {
    event.preventDefault()
  }
}

const pdfContainer = ref<HTMLElement | null>(null)
const pdfLoading = ref(false)
const pdfError = ref<string | null>(null)
let pdfLoadToken = 0
let pdfCleanup: (() => void) | null = null
let pdfAbort: AbortController | null = null

function markOfficePreviewFailed(): void {
  previewConversionFailed.value = true
  pdfError.value = String(t('showcase.detail.legacyDocHint'))
}

watch(
  officePreviewPending,
  (pending) => {
    clearOfficePendingTimer()
    if (!pending) return
    if (typeof EventSource === 'undefined') {
      markOfficePreviewFailed()
      return
    }
    officePendingTimer = setTimeout(() => {
      if (
        isOfficeKind.value &&
        !absolutePreviewUrl.value &&
        !previewConversionFailed.value
      ) {
        markOfficePreviewFailed()
      }
    }, OFFICE_PENDING_TIMEOUT_MS)
  },
  { immediate: true }
)

function measureContentWidth(): number {
  if (showPdfReader.value && pdfContainer.value) {
    const page = pdfContainer.value.querySelector<HTMLElement>('.showcase-pdf-page, canvas')
    return page?.scrollWidth || pdfContainer.value.scrollWidth
  }
  return 0
}

function recomputeFitZoom(): void {
  const viewport = viewportEl.value
  if (!viewport) return
  // px-3 padding on the PDF host wrapper
  const available = viewport.clientWidth - 24
  if (available <= 0) return

  // Measure at fitZoom=1; do not touch userZoom (avoids pdf.js re-raster).
  fitZoom.value = 1
  void nextTick(() => {
    const natural = measureContentWidth()
    fitZoom.value =
      natural > available + 2 ? Math.max(ZOOM_MIN, Math.min(1, available / natural)) : 1
  })
}

async function loadPdfPreview(url: string, container: HTMLElement): Promise<void> {
  pdfAbort?.abort()
  pdfAbort = new AbortController()
  pdfCleanup?.()
  pdfCleanup = null
  container.replaceChildren()

  // Page width is natural CSS px (max-width:100%); userZoom changes raster scale.
  pdfCleanup = await renderPdfPreview({
    url,
    container,
    scale: PDF_BASE_SCALE * userZoom.value,
    signal: pdfAbort.signal,
    watermarkText: watermarkText.value,
  })
}

watch(
  [pdfSourceUrl, showPdfReader, () => pdfContainer.value, userZoom, officePreviewPending],
  async ([url, usesPdfReader, container, , pending]) => {
    if (!usesPdfReader || !container || pending || !url) {
      pdfAbort?.abort()
      pdfAbort = null
      pdfCleanup?.()
      pdfCleanup = null
      pdfLoading.value = false
      if (!pending) {
        // Keep conversion-fail message when Office preview is missing.
        if (!(isOfficeKind.value && previewConversionFailed.value && !url)) {
          pdfError.value = null
        }
      } else {
        pdfError.value = null
      }
      if (usesPdfReader && !pending) {
        container?.replaceChildren()
      }
      return
    }

    const token = ++pdfLoadToken
    pdfLoading.value = true
    pdfError.value = null

    try {
      await loadPdfPreview(url, container)
      if (token !== pdfLoadToken) return
      await nextTick()
      // Fit narrow viewports; userZoom stays for sharp re-raster.
      recomputeFitZoom()
    } catch (e) {
      if (token !== pdfLoadToken) return
      if (e instanceof DOMException && e.name === 'AbortError') return
      pdfError.value = String(t('showcase.detail.docPreviewFailed'))
    } finally {
      if (token === pdfLoadToken) {
        pdfLoading.value = false
      }
    }
  },
  { immediate: true, flush: 'post' }
)

watch(
  () => [props.attachmentUrl, props.previewUrl] as const,
  () => {
    fitZoom.value = 1
    userZoom.value = 1
  }
)

let resizeObserver: ResizeObserver | null = null
let offCoverFail: (() => void) | null = null

onMounted(() => {
  document.addEventListener('fullscreenchange', syncFullscreenState)
  if (viewportEl.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      if (userZoom.value === 1) {
        recomputeFitZoom()
      }
    })
    resizeObserver.observe(viewportEl.value)
  }
  offCoverFail = eventBus.on('showcase:cover_fail', ({ postId }) => {
    if (!props.postId || props.postId !== postId) return
    if (absolutePreviewUrl.value) return
    markOfficePreviewFailed()
  })
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', syncFullscreenState)
  clearOfficePendingTimer()
  offCoverFail?.()
  offCoverFail = null
  resizeObserver?.disconnect()
  resizeObserver = null
  pdfAbort?.abort()
  pdfAbort = null
  pdfCleanup?.()
  pdfCleanup = null
  if (document.fullscreenElement === readerRoot.value) {
    void document.exitFullscreen()
  }
})
</script>

<template>
  <div
    ref="readerRoot"
    class="showcase-doc-reader flex h-full min-h-0 flex-col bg-white"
    :class="{ 'showcase-doc-reader--fullscreen': isFullscreen }"
  >
    <div
      v-if="hasReaderContent"
      class="flex shrink-0 items-center justify-end gap-1 border-b border-gray-100 px-3 py-1.5"
    >
      <button
        type="button"
        class="doc-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-40"
        :disabled="zoomLevel <= ZOOM_MIN + 0.001 || officePreviewPending"
        :title="String(t('showcase.detail.zoomOut'))"
        @click="zoomOut"
      >
        <ZoomOut class="h-3.5 w-3.5" />
      </button>
      <span class="min-w-11 text-center text-xs tabular-nums text-gray-500">{{ zoomPercent }}</span>
      <button
        type="button"
        class="doc-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-40"
        :disabled="zoomLevel >= ZOOM_MAX - 0.001 || officePreviewPending"
        :title="String(t('showcase.detail.zoomIn'))"
        @click="zoomIn"
      >
        <ZoomIn class="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        class="doc-reader-toolbar-btn rounded-lg px-2 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-800"
        :disabled="officePreviewPending"
        :title="String(t('showcase.detail.zoomReset'))"
        @click="resetZoom"
      >
        {{ t('showcase.detail.zoomReset') }}
      </button>
      <span class="mx-1 h-4 w-px bg-gray-200" />
      <button
        type="button"
        class="doc-reader-toolbar-btn inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-800"
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
      ref="viewportEl"
      class="showcase-doc-viewport relative min-h-0 flex-1 overflow-x-hidden overflow-y-auto bg-white"
      @copy="blockCopyEvent"
      @cut="blockCopyEvent"
      @selectstart="blockCopyEvent"
      @contextmenu="blockCopyEvent"
      @keydown="blockCopyKeydown"
      @dragstart="blockCopyEvent"
    >
      <div
        v-if="showPdfReader"
        class="relative min-h-full px-3 py-3"
        :style="fitZoomStyle"
      >
        <div
          v-if="officePreviewPending || pdfLoading"
          class="absolute inset-0 z-10 flex items-center justify-center bg-white/80 text-gray-500"
        >
          <Loader2 class="mr-2 h-5 w-5 animate-spin" />
          <span class="text-sm">{{
            officePreviewPending
              ? t('showcase.detail.officePreviewPending')
              : t('showcase.detail.docPreviewLoading')
          }}</span>
        </div>
        <div
          v-if="pdfError && !officePreviewPending"
          class="absolute inset-0 z-20 flex min-h-[50vh] flex-col items-center justify-center gap-3 bg-white px-8 text-center"
        >
          <FileText class="h-12 w-12 text-gray-300" />
          <p class="text-sm text-gray-500">{{ pdfError }}</p>
        </div>
        <div
          v-show="!officePreviewPending"
          ref="pdfContainer"
          class="showcase-pdf-host mx-auto w-full max-w-full"
        />
      </div>

      <div
        v-else-if="fallbackText && !hasAttachmentPreview"
        class="showcase-doc-fallback showcase-watermark-host relative px-8 py-6 whitespace-pre-line"
        :style="contentZoomStyle"
      >
        <div v-if="watermarkText" class="showcase-page-watermark" aria-hidden="true">
          <span v-for="tile in watermarkTiles" :key="tile">{{ watermarkText }}</span>
        </div>
        {{ fallbackText }}
      </div>

      <div
        v-else-if="!hasAttachmentPreview"
        class="flex min-h-[50vh] flex-col items-center justify-center px-6 pb-8 text-center text-gray-400"
      >
        <FileText class="mb-3 h-12 w-12 text-gray-300" />
        <p class="text-sm">{{ t('showcase.detail.noDocument') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.showcase-doc-fallback {
  font-size: 0.875rem;
  line-height: 1.75;
  color: #374151;
  user-select: none;
  -webkit-user-select: none;
}

.showcase-doc-fallback :deep(p) {
  margin-bottom: 0.75rem;
}

.showcase-doc-fallback :deep(h1),
.showcase-doc-fallback :deep(h2),
.showcase-doc-fallback :deep(h3) {
  margin-bottom: 0.5rem;
  font-weight: 600;
  color: #111827;
}

.doc-reader-toolbar-btn {
  border: none;
  outline: none;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.doc-reader-toolbar-btn:focus,
.doc-reader-toolbar-btn:focus-visible {
  outline: none;
}

.showcase-doc-viewport {
  user-select: none;
  -webkit-user-select: none;
}

:deep(.showcase-watermark-host) {
  position: relative;
  overflow: hidden;
}

:deep(.showcase-page-watermark) {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: 6.25rem;
  align-content: start;
  gap: 0.35rem 0.5rem;
  padding: 1.25rem 0.5rem;
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
  opacity: 0.16;
}

.showcase-pdf-host :deep(.showcase-pdf-page) {
  max-width: 100%;
  height: auto !important;
}

.showcase-pdf-host :deep(.showcase-pdf-page-wrap) {
  max-width: 100%;
}

.showcase-pdf-host :deep(.showcase-pdf-frame) {
  min-height: 70vh;
}

.showcase-doc-reader:fullscreen {
  width: 100%;
  height: 100%;
  background: #fff;
}

.showcase-doc-reader:fullscreen .showcase-doc-viewport {
  height: 100%;
}
</style>
