<script setup lang="ts">
/**
 * Doubao-style middle pane: open seminar resources / diagram artifacts.
 * PDF and Office files render via LibreOffice→PDF + pdf.js.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { Download, FileText, Loader2, Maximize2, Minimize2, Quote, X } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import ImagePreviewModal from '@/components/common/ImagePreviewModal.vue'
import ShowcaseInlineDiagramPreview from '@/components/showcase/ShowcaseInlineDiagramPreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  type SeminarDocTab,
  citeSeminarFile,
  closeSeminarDoc,
  focusSeminarDoc,
  seminarDocActiveId,
  seminarDocActiveTab,
  seminarDocFullscreen,
  seminarDocTabs,
  seminarOfficePreviewFileId,
  seminarSpectator,
  toggleSeminarDocFullscreen,
} from '@/composables/mindmate/mindmateSeminarChrome'
import {
  type SharedCanvasDiagramPreview,
  fetchSharedCanvasDiagramPreview,
} from '@/utils/mindmateSeminarDiagramLibrary'
import {
  type SeminarBackgroundFile,
  type SeminarFilePreviewMode,
  downloadSeminarBackgroundFile,
  fetchSeminarBackgroundBlob,
  fetchSeminarBackgroundPreviewPdf,
  seminarFilePreviewMode,
} from '@/utils/mindmateSeminarFolder'
import { renderPdfFromBytes } from '@/utils/renderPdfPreview'

const props = defineProps<{
  sessionId: string
}>()

const { t } = useLanguage()
const notify = useNotifications()

const loading = ref(false)
const imageOpen = ref(false)
const converting = ref(false)
const objectUrl = ref('')
const textBody = ref('')
const previewMode = ref<SeminarFilePreviewMode | 'diagram' | 'canvas'>('unsupported')
const canvasPreview = ref<SharedCanvasDiagramPreview | null>(null)
const pdfHost = ref<HTMLElement | null>(null)
let pdfCleanup: (() => void) | null = null
let loadAbort: AbortController | null = null

const activeTab = seminarDocActiveTab
const tabs = seminarDocTabs

const title = computed(() => activeTab.value?.title || t('mindmate.docViewer.title'))

function revokeObjectUrl(): void {
  if (objectUrl.value && objectUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(objectUrl.value)
  }
  objectUrl.value = ''
}

function clearPdf(): void {
  if (pdfCleanup) {
    pdfCleanup()
    pdfCleanup = null
  }
  if (pdfHost.value) {
    pdfHost.value.replaceChildren()
  }
}

async function renderPdfBytes(data: Uint8Array, signal: AbortSignal): Promise<void> {
  await nextTick()
  if (!pdfHost.value || signal.aborted) {
    return
  }
  clearPdf()
  pdfCleanup = await renderPdfFromBytes(data, pdfHost.value, { scale: 1.35, signal })
}

async function loadActiveTab(tab: SeminarDocTab | null): Promise<void> {
  loadAbort?.abort()
  if (seminarOfficePreviewFileId.value && seminarOfficePreviewFileId.value !== tab?.fileId) {
    seminarOfficePreviewFileId.value = null
  }
  const abort = new AbortController()
  loadAbort = abort
  revokeObjectUrl()
  clearPdf()
  imageOpen.value = false
  textBody.value = ''
  converting.value = false
  canvasPreview.value = null
  if (!tab) {
    previewMode.value = 'unsupported'
    return
  }
  if (tab.diagramId) {
    previewMode.value = 'canvas'
    loading.value = true
    canvasPreview.value = await fetchSharedCanvasDiagramPreview(props.sessionId, tab.diagramId)
    loading.value = false
    if (!canvasPreview.value) {
      previewMode.value = 'unsupported'
    }
    return
  }
  if (tab.kind === 'diagram') {
    previewMode.value = 'diagram'
    objectUrl.value = tab.imagePath || ''
    return
  }
  if (!props.sessionId || !tab.fileId) {
    previewMode.value = 'unsupported'
    return
  }
  loading.value = true
  try {
    const mode = seminarFilePreviewMode(tab.contentType || '', tab.filename || tab.title)
    previewMode.value = mode
    if (mode === 'text') {
      const blob = await fetchSeminarBackgroundBlob(props.sessionId, tab.fileId)
      if (abort.signal.aborted) {
        return
      }
      textBody.value = await blob.text()
      return
    }
    if (mode === 'image') {
      const blob = await fetchSeminarBackgroundBlob(props.sessionId, tab.fileId)
      if (abort.signal.aborted) {
        return
      }
      objectUrl.value = URL.createObjectURL(blob)
      return
    }
    if (mode === 'pdf' || mode === 'office') {
      converting.value = mode === 'office'
      if (mode === 'office' && tab.fileId) {
        seminarOfficePreviewFileId.value = tab.fileId
      }
      const data = await fetchSeminarBackgroundPreviewPdf(props.sessionId, tab.fileId)
      if (abort.signal.aborted) {
        return
      }
      converting.value = false
      await renderPdfBytes(data, abort.signal)
      return
    }
    previewMode.value = 'unsupported'
  } catch (error) {
    if (abort.signal.aborted) {
      return
    }
    converting.value = false
    previewMode.value = 'unsupported'
    const message = error instanceof Error ? error.message : ''
    if (message.includes('preview_failed') || message.includes('503')) {
      notify.errorKey('mindmate.docViewer.convertFailed')
    } else {
      notify.errorKey('mindmate.docViewer.loadFailed')
    }
  } finally {
    if (tab?.fileId && seminarOfficePreviewFileId.value === tab.fileId && !abort.signal.aborted) {
      seminarOfficePreviewFileId.value = null
    }
    if (!abort.signal.aborted) {
      loading.value = false
      converting.value = false
    }
  }
}

async function downloadActive(): Promise<void> {
  const tab = activeTab.value
  if (!tab || tab.kind !== 'file' || !tab.fileId || !props.sessionId) {
    return
  }
  const file: SeminarBackgroundFile = {
    id: tab.fileId,
    filename: tab.filename || tab.title,
    contentType: tab.contentType || 'application/octet-stream',
    sizeBytes: 0,
    uploaderName: '',
    pinned: false,
    pinnedAt: null,
    createdAt: '',
    sourceMessageId: null,
    listed: false,
    artifact: false,
    diagramId: null,
  }
  try {
    await downloadSeminarBackgroundFile(props.sessionId, file)
  } catch {
    notify.errorKey('mindmate.folder.loadFailed')
  }
}

function citeActive(): void {
  const tab = activeTab.value
  if (!tab || tab.kind !== 'file' || !tab.fileId) {
    return
  }
  citeSeminarFile({
    fileId: tab.fileId,
    filename: tab.filename || tab.title,
    contentType: tab.contentType || 'application/octet-stream',
    sizeBytes: 0,
  })
  notify.successKey('mindmate.docViewer.cited')
}

function onCloseTab(id: string, event?: Event): void {
  event?.stopPropagation()
  closeSeminarDoc(id)
}

watch(
  () => [activeTab.value?.id, props.sessionId] as const,
  () => {
    void loadActiveTab(activeTab.value)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  const fileId = activeTab.value?.fileId ?? null
  loadAbort?.abort()
  if (fileId && seminarOfficePreviewFileId.value === fileId) {
    seminarOfficePreviewFileId.value = null
  }
  revokeObjectUrl()
  clearPdf()
})
</script>

<template>
  <section
    class="mm-doc-viewer"
    :aria-label="t('mindmate.docViewer.title')"
  >
    <header class="mm-doc-viewer__tabs">
      <div
        class="mm-doc-viewer__tab-list"
        role="tablist"
      >
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          class="mm-doc-viewer__tab"
          :class="{ 'is-active': tab.id === seminarDocActiveId }"
          :aria-selected="tab.id === seminarDocActiveId"
          @click="focusSeminarDoc(tab.id)"
        >
          <FileText
            :size="13"
            class="mm-doc-viewer__tab-icon"
            aria-hidden="true"
          />
          <span class="mm-doc-viewer__tab-title">{{ tab.title }}</span>
          <span
            class="mm-doc-viewer__tab-close"
            role="button"
            tabindex="0"
            :aria-label="t('common.close')"
            @click="onCloseTab(tab.id, $event)"
            @keydown.enter.prevent="onCloseTab(tab.id)"
          >
            <X
              :size="12"
              aria-hidden="true"
            />
          </span>
        </button>
      </div>
    </header>

    <div class="mm-doc-viewer__toolbar">
      <div class="mm-doc-viewer__crumb">
        <span class="mm-doc-viewer__crumb-name">{{ title }}</span>
      </div>
      <div class="mm-doc-viewer__actions">
        <button
          v-if="activeTab?.kind === 'file' && !seminarSpectator"
          type="button"
          class="mm-doc-viewer__action"
          :aria-label="t('mindmate.docViewer.cite')"
          @click="citeActive"
        >
          <Quote
            :size="14"
            aria-hidden="true"
          />
          <I18nText
            k="mindmate.docViewer.cite"
            dense
          />
        </button>
        <button
          v-if="activeTab?.kind === 'file' && !seminarSpectator"
          type="button"
          class="mm-doc-viewer__action"
          :aria-label="t('mindmate.docViewer.download')"
          @click="downloadActive"
        >
          <Download
            :size="14"
            aria-hidden="true"
          />
          <I18nText
            k="mindmate.docViewer.download"
            dense
          />
        </button>
        <button
          type="button"
          class="mm-doc-viewer__action mm-doc-viewer__action--icon"
          :aria-label="
            seminarDocFullscreen
              ? t('mindmate.docViewer.exitFullscreen')
              : t('mindmate.docViewer.fullscreen')
          "
          @click="toggleSeminarDocFullscreen()"
        >
          <Minimize2
            v-if="seminarDocFullscreen"
            :size="15"
            aria-hidden="true"
          />
          <Maximize2
            v-else
            :size="15"
            aria-hidden="true"
          />
        </button>
      </div>
    </div>

    <div class="mm-doc-viewer__body">
      <div
        v-if="loading || converting"
        class="mm-doc-viewer__pending"
      >
        <Loader2
          :size="22"
          class="mm-doc-viewer__spin"
          aria-hidden="true"
        />
        <p class="mm-doc-viewer__empty">
          <I18nText :k="converting ? 'mindmate.docViewer.converting' : 'common.loading'" />
        </p>
      </div>
      <div
        v-else-if="previewMode === 'canvas' && canvasPreview"
        class="mm-doc-viewer__canvas"
      >
        <ShowcaseInlineDiagramPreview
          browse
          tight-fit
          :spec="canvasPreview.spec"
          :diagram-type="canvasPreview.diagramType"
        />
      </div>
      <img
        v-else-if="previewMode === 'image' || previewMode === 'diagram'"
        class="mm-doc-viewer__image"
        :class="{ 'is-zoomable': previewMode === 'image' }"
        :src="objectUrl"
        :alt="title"
        @click="previewMode === 'image' && (imageOpen = true)"
      />
      <ImagePreviewModal
        v-if="previewMode === 'image' && objectUrl"
        v-model:visible="imageOpen"
        :title="title"
        :image-url="objectUrl"
      />
      <pre
        v-else-if="previewMode === 'text'"
        class="mm-doc-viewer__text"
        >{{ textBody }}</pre>
      <div
        v-show="previewMode === 'pdf' || previewMode === 'office'"
        ref="pdfHost"
        class="mm-doc-viewer__pdf"
      />
      <div
        v-if="!loading && !converting && previewMode === 'unsupported'"
        class="mm-doc-viewer__unsupported"
      >
        <p class="mm-doc-viewer__empty">
          <I18nText k="mindmate.docViewer.unsupported" />
        </p>
        <button
          v-if="activeTab?.kind === 'file' && !seminarSpectator"
          type="button"
          class="mm-doc-viewer__action"
          @click="downloadActive"
        >
          <Download
            :size="14"
            aria-hidden="true"
          />
          <I18nText
            k="mindmate.docViewer.download"
            dense
          />
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.mm-doc-viewer {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  background: #fff;
  border-left: 1px solid #e8e4df;
}

.mm-doc-viewer__tabs {
  flex-shrink: 0;
  border-bottom: 1px solid #efeae4;
  background: #faf8f5;
  overflow: hidden;
}

.mm-doc-viewer__tab-list {
  display: flex;
  align-items: stretch;
  gap: 0;
  overflow-x: auto;
  padding: 0 4px;
}

.mm-doc-viewer__tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 11rem;
  height: 36px;
  padding: 0 10px 0 12px;
  border: none;
  border-right: 1px solid #efeae4;
  background: transparent;
  color: #78716c;
  font-size: 12px;
  cursor: pointer;
}

.mm-doc-viewer__tab.is-active {
  background: #fff;
  color: #1c1917;
  box-shadow: inset 0 -2px 0 #5b8def;
}

.mm-doc-viewer__tab-icon {
  flex-shrink: 0;
  opacity: 0.7;
}

.mm-doc-viewer__tab-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-doc-viewer__tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 4px;
  color: #a8a29e;
  flex-shrink: 0;
}

.mm-doc-viewer__tab-close:hover {
  background: #f5f5f4;
  color: #44403c;
}

.mm-doc-viewer__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
  min-height: 40px;
  padding: 0 12px;
  border-bottom: 1px solid #f0ebe6;
}

.mm-doc-viewer__crumb-name {
  font-size: 13px;
  font-weight: 600;
  color: #292524;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-doc-viewer__actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.mm-doc-viewer__action {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 10px;
  border: none;
  border-radius: 8px;
  background: #f5f5f4;
  color: #57534e;
  font-size: 12px;
  cursor: pointer;
}

.mm-doc-viewer__action:hover {
  color: #5b21b6;
  background: #f5f3ff;
}

.mm-doc-viewer__action--icon {
  width: 28px;
  padding: 0;
  justify-content: center;
  background: transparent;
}

.mm-doc-viewer__action--icon:hover {
  background: #f5f5f4;
}

.mm-doc-viewer__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: #f7f5f2;
  display: flex;
  flex-direction: column;
}

.mm-doc-viewer__pending {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 16px;
}

.mm-doc-viewer__spin {
  color: #8b5cf6;
  animation: mm-doc-spin 0.9s linear infinite;
}

@keyframes mm-doc-spin {
  to {
    transform: rotate(360deg);
  }
}

.mm-doc-viewer__empty {
  margin: 0;
  padding: 8px 16px;
  font-size: 13px;
  color: #a8a29e;
  text-align: center;
}

.mm-doc-viewer__image {
  display: block;
  flex-shrink: 0;
  max-width: 100%;
  width: auto;
  height: auto;
  margin: 16px auto;
  background: #fff;
  box-shadow: 0 1px 8px rgba(28, 25, 23, 0.06);
}

.mm-doc-viewer__image.is-zoomable {
  cursor: zoom-in;
}

.mm-doc-viewer__pdf {
  flex: 1;
  min-height: 100%;
  padding: 12px 10px 24px;
}

.mm-doc-viewer__canvas {
  flex: 1;
  min-height: 280px;
  height: 100%;
}

.mm-doc-viewer__text {
  margin: 0;
  padding: 16px 18px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #1c1917;
  background: #fff;
  min-height: 100%;
}

.mm-doc-viewer__unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 16px;
}
</style>
