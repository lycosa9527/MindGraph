<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { FileText, Loader2, Maximize2, Minimize2, ZoomIn, ZoomOut } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { renderDocxPreview } from '@/utils/renderDocxPreview'
import { renderPdfPreview } from '@/utils/renderPdfPreview'

const props = defineProps<{
  attachmentUrl?: string | null
  fallbackText?: string
  watermarkName?: string | null
  watermarkOrganization?: string | null
}>()

const { t } = useLanguage()

type FileKind = 'pdf' | 'docx' | 'doc' | 'unknown'

const WATERMARK_TILE_COUNT = 18
const PDF_BASE_SCALE = 1.35
const ZOOM_MIN = 0.6
const ZOOM_MAX = 2.5
const ZOOM_STEP = 0.15

const fileKind = computed<FileKind>(() => {
  const url = props.attachmentUrl?.toLowerCase() ?? ''
  if (url.endsWith('.pdf')) return 'pdf'
  if (url.endsWith('.docx')) return 'docx'
  if (url.endsWith('.doc')) return 'doc'
  return 'unknown'
})

const absoluteAttachmentUrl = computed(() => {
  if (!props.attachmentUrl || typeof window === 'undefined') return null
  return new URL(props.attachmentUrl, window.location.origin).href
})

const watermarkText = computed(() => {
  const name = props.watermarkName?.trim()
  const org = props.watermarkOrganization?.trim()
  if (name && org) return `${name} · ${org}`
  return name || org || ''
})

const watermarkTiles = computed(() =>
  watermarkText.value ? Array.from({ length: WATERMARK_TILE_COUNT }, (_, i) => i) : []
)

function isPublicHttpsUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:') return false
    const host = parsed.hostname.toLowerCase()
    if (host === 'localhost' || host === '127.0.0.1' || host.endsWith('.local')) return false
    if (host.startsWith('10.') || host.startsWith('192.168.') || host.startsWith('172.')) return false
    return true
  } catch {
    return false
  }
}

const legacyDocOfficeSrc = computed(() => {
  if (!absoluteAttachmentUrl.value || fileKind.value !== 'doc') return null
  if (!isPublicHttpsUrl(absoluteAttachmentUrl.value)) return null
  return `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(absoluteAttachmentUrl.value)}`
})

const hasAttachmentPreview = computed(
  () =>
    fileKind.value === 'pdf' ||
    fileKind.value === 'docx' ||
    Boolean(legacyDocOfficeSrc.value)
)

const hasReaderContent = computed(
  () => hasAttachmentPreview.value || Boolean(props.fallbackText?.trim())
)

const zoomLevel = ref(1)

const zoomPercent = computed(() => `${Math.round(zoomLevel.value * 100)}%`)

const contentZoomStyle = computed(() => ({
  transform: `scale(${zoomLevel.value})`,
  transformOrigin: 'top center',
}))

function zoomIn() {
  zoomLevel.value = Math.min(ZOOM_MAX, Math.round((zoomLevel.value + ZOOM_STEP) * 100) / 100)
}

function zoomOut() {
  zoomLevel.value = Math.max(ZOOM_MIN, Math.round((zoomLevel.value - ZOOM_STEP) * 100) / 100)
}

function resetZoom() {
  zoomLevel.value = 1
}

const readerRoot = ref<HTMLElement | null>(null)
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

const docxContainer = ref<HTMLElement | null>(null)
const docxLoading = ref(false)
const docxError = ref<string | null>(null)
let docxLoadToken = 0

const pdfContainer = ref<HTMLElement | null>(null)
const pdfLoading = ref(false)
const pdfError = ref<string | null>(null)
let pdfLoadToken = 0
let pdfCleanup: (() => void) | null = null
let pdfAbort: AbortController | null = null

async function loadPdfPreview(url: string, container: HTMLElement): Promise<void> {
  pdfAbort?.abort()
  pdfAbort = new AbortController()
  pdfCleanup?.()
  pdfCleanup = null
  container.replaceChildren()

  pdfCleanup = await renderPdfPreview({
    url,
    container,
    scale: PDF_BASE_SCALE * zoomLevel.value,
    signal: pdfAbort.signal,
    watermarkText: watermarkText.value,
  })
}

watch(
  [absoluteAttachmentUrl, fileKind, () => pdfContainer.value, zoomLevel],
  async ([url, kind, container]) => {
    if (kind !== 'pdf' || !url || !container) {
      pdfAbort?.abort()
      pdfAbort = null
      pdfCleanup?.()
      pdfCleanup = null
      pdfLoading.value = false
      pdfError.value = null
      container?.replaceChildren()
      return
    }

    const token = ++pdfLoadToken
    pdfLoading.value = true
    pdfError.value = null

    try {
      await loadPdfPreview(url, container)
      if (token !== pdfLoadToken) return
    } catch (e) {
      if (token !== pdfLoadToken) return
      if (e instanceof DOMException && e.name === 'AbortError') return
      pdfError.value = String(t('caseSquare.detail.docPreviewFailed'))
    } finally {
      if (token === pdfLoadToken) {
        pdfLoading.value = false
      }
    }
  },
  { immediate: true, flush: 'post' }
)

watch(
  [absoluteAttachmentUrl, fileKind, () => docxContainer.value],
  async ([url, kind, container]) => {
    if (kind !== 'docx' || !url || !container) {
      docxLoading.value = false
      docxError.value = null
      container?.replaceChildren()
      return
    }

    const token = ++docxLoadToken
    docxLoading.value = true
    docxError.value = null
    container.replaceChildren()

    try {
      const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}mg_preview=${Date.now()}`, {
        credentials: 'include',
        cache: 'no-store',
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const blob = await response.blob()
      if (token !== docxLoadToken || !container) return
      await renderDocxPreview(blob, container, watermarkText.value)
    } catch {
      if (token !== docxLoadToken) return
      docxError.value = String(t('caseSquare.detail.docPreviewFailed'))
    } finally {
      if (token === docxLoadToken) {
        docxLoading.value = false
      }
    }
  },
  { immediate: true, flush: 'post' }
)

watch(
  () => props.attachmentUrl,
  () => {
    zoomLevel.value = 1
  }
)

onMounted(() => {
  document.addEventListener('fullscreenchange', syncFullscreenState)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', syncFullscreenState)
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
    class="case-square-doc-reader flex h-full min-h-0 flex-col bg-white"
    :class="{ 'case-square-doc-reader--fullscreen': isFullscreen }"
  >
    <div
      v-if="hasReaderContent"
      class="flex shrink-0 items-center justify-end gap-1 border-b border-gray-100 px-3 py-1.5"
    >
      <button
        type="button"
        class="doc-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-40"
        :disabled="zoomLevel <= ZOOM_MIN"
        :title="String(t('caseSquare.detail.zoomOut'))"
        @click="zoomOut"
      >
        <ZoomOut class="h-3.5 w-3.5" />
      </button>
      <span class="min-w-[2.75rem] text-center text-xs tabular-nums text-gray-500">{{ zoomPercent }}</span>
      <button
        type="button"
        class="doc-reader-toolbar-btn inline-flex items-center justify-center rounded-lg p-1.5 text-gray-500 hover:bg-gray-50 hover:text-gray-800 disabled:opacity-40"
        :disabled="zoomLevel >= ZOOM_MAX"
        :title="String(t('caseSquare.detail.zoomIn'))"
        @click="zoomIn"
      >
        <ZoomIn class="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        class="doc-reader-toolbar-btn rounded-lg px-2 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-800"
        @click="resetZoom"
      >
        {{ t('caseSquare.detail.zoomReset') }}
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
            ? t('caseSquare.detail.exitFullscreen')
            : t('caseSquare.detail.enterFullscreen')
        }}
      </button>
    </div>

    <div
      class="case-square-doc-viewport relative min-h-0 flex-1 overflow-auto bg-white"
      @copy="blockCopyEvent"
      @cut="blockCopyEvent"
      @selectstart="blockCopyEvent"
      @contextmenu="blockCopyEvent"
      @keydown="blockCopyKeydown"
      @dragstart="blockCopyEvent"
    >
      <div
        v-if="fileKind === 'pdf'"
        class="relative min-h-full px-4 py-4"
        :style="contentZoomStyle"
      >
        <div
          v-if="pdfLoading"
          class="absolute inset-0 z-10 flex items-center justify-center bg-white/80 text-gray-500"
        >
          <Loader2 class="mr-2 h-5 w-5 animate-spin" />
          <span class="text-sm">{{ t('caseSquare.detail.docPreviewLoading') }}</span>
        </div>
        <div
          v-if="pdfError"
          class="absolute inset-0 z-20 flex min-h-[50vh] flex-col items-center justify-center gap-3 bg-white px-8 text-center"
        >
          <FileText class="h-12 w-12 text-gray-300" />
          <p class="text-sm text-gray-500">{{ pdfError }}</p>
        </div>
        <div ref="pdfContainer" class="case-square-pdf-host mx-auto max-w-3xl" />
      </div>

      <div v-else-if="fileKind === 'docx'" class="relative min-h-full" :style="contentZoomStyle">
        <div
          v-if="docxLoading"
          class="absolute inset-0 z-10 flex items-center justify-center bg-white/80 text-gray-500"
        >
          <Loader2 class="mr-2 h-5 w-5 animate-spin" />
          <span class="text-sm">{{ t('caseSquare.detail.docPreviewLoading') }}</span>
        </div>
        <div
          v-if="docxError"
          class="absolute inset-0 z-20 flex min-h-[50vh] flex-col items-center justify-center gap-3 bg-white px-8 text-center"
        >
          <FileText class="h-12 w-12 text-gray-300" />
          <p class="text-sm text-gray-500">{{ docxError }}</p>
        </div>
        <div ref="docxContainer" class="case-square-docx-host px-4 py-4" />
      </div>

      <iframe
        v-else-if="legacyDocOfficeSrc"
        :src="legacyDocOfficeSrc"
        :title="t('caseSquare.detail.docPreview')"
        class="block min-h-full w-full border-0"
      />

      <div
        v-else-if="fileKind === 'doc'"
        class="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-8 pb-8 text-center"
      >
        <FileText class="h-12 w-12 text-gray-300" />
        <p class="text-sm text-gray-500">{{ t('caseSquare.detail.legacyDocHint') }}</p>
      </div>

      <div
        v-else-if="fallbackText && !hasAttachmentPreview"
        class="case-square-doc-fallback case-square-watermark-host relative px-8 py-6 whitespace-pre-line"
        :style="contentZoomStyle"
      >
        <div v-if="watermarkText" class="case-square-page-watermark" aria-hidden="true">
          <span v-for="tile in watermarkTiles" :key="tile">{{ watermarkText }}</span>
        </div>
        {{ fallbackText }}
      </div>

      <div
        v-else-if="!hasAttachmentPreview"
        class="flex min-h-[50vh] flex-col items-center justify-center px-6 pb-8 text-center text-gray-400"
      >
        <FileText class="mb-3 h-12 w-12 text-gray-300" />
        <p class="text-sm">{{ t('caseSquare.detail.noDocument') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.case-square-doc-fallback {
  font-size: 0.875rem;
  line-height: 1.75;
  color: #374151;
  user-select: none;
  -webkit-user-select: none;
}

.case-square-doc-fallback :deep(p) {
  margin-bottom: 0.75rem;
}

.case-square-doc-fallback :deep(h1),
.case-square-doc-fallback :deep(h2),
.case-square-doc-fallback :deep(h3) {
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

.case-square-doc-viewport {
  user-select: none;
  -webkit-user-select: none;
}

:deep(.case-square-watermark-host) {
  position: relative;
}

:deep(.case-square-page-watermark) {
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

:deep(.case-square-page-watermark span) {
  transform: rotate(-22deg);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.3;
  color: #6b7280;
  text-align: center;
  white-space: nowrap;
  opacity: 0.14;
}

.case-square-doc-watermark {
  display: none;
}

.case-square-docx-host :deep(.case-square-docx-wrapper),
.case-square-docx-host :deep(.case-square-docx),
.case-square-docx-host :deep(section),
.case-square-docx-host :deep(article),
.case-square-docx-host :deep(.docx) {
  background: #fff !important;
  background-color: #fff !important;
  color: #111827;
}

.case-square-docx-host :deep(.case-square-docx-wrapper) {
  margin: 0 auto;
  box-shadow:
    0 1px 3px rgb(0 0 0 / 6%),
    0 4px 12px rgb(0 0 0 / 4%);
}

.case-square-docx-host :deep(p),
.case-square-docx-host :deep(span),
.case-square-docx-host :deep(td),
.case-square-docx-host :deep(th),
.case-square-docx-host :deep(li) {
  user-select: none;
  -webkit-user-select: none;
}

.case-square-pdf-host :deep(.case-square-pdf-page) {
  max-width: 100%;
  height: auto !important;
}

.case-square-pdf-host :deep(.case-square-pdf-frame) {
  min-height: 70vh;
}

.case-square-doc-reader:fullscreen {
  width: 100%;
  height: 100%;
  background: #fff;
}

.case-square-doc-reader:fullscreen .case-square-doc-viewport {
  height: 100%;
}
</style>
