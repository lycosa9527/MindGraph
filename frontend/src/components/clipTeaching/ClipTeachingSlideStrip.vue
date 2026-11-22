<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import type { ClipPreviewStatus } from '@/utils/clipTeachingApi'
import { fetchClipPreview } from '@/utils/clipTeachingApi'

const props = defineProps<{
  lessonId: string
  status: ClipPreviewStatus
  canEdit: boolean
  busy: boolean
}>()

const emit = defineEmits<{
  upload: [file: File]
}>()

const { t } = useLanguage()
const thumbs = ref<string[]>([])
const selected = ref<number | null>(null)
const dialogCanvas = ref<HTMLCanvasElement | null>(null)
let pdfBytes: Uint8Array | null = null
let loadGen = 0

function onFile(event: Event): void {
  const input = event.target
  if (!(input instanceof HTMLInputElement) || !input.files?.[0]) return
  emit('upload', input.files[0])
  input.value = ''
}

async function renderPage(
  pageNumber: number,
  scale: number,
  canvas: HTMLCanvasElement
): Promise<void> {
  if (!pdfBytes) return
  const pdfjs = await import('pdfjs-dist')
  const base = import.meta.env.BASE_URL.replace(/\/?$/, '/')
  pdfjs.GlobalWorkerOptions.workerSrc = `${base}pdf.worker.min.mjs`
  const pdf = await pdfjs.getDocument({ data: pdfBytes.slice() }).promise
  const page = await pdf.getPage(pageNumber)
  const viewport = page.getViewport({ scale })
  canvas.width = Math.floor(viewport.width)
  canvas.height = Math.floor(viewport.height)
  const context = canvas.getContext('2d')
  if (!context) {
    await pdf.cleanup()
    return
  }
  await page.render({ canvas, canvasContext: context, viewport }).promise
  await pdf.cleanup()
}

async function loadThumbs(): Promise<void> {
  const gen = ++loadGen
  thumbs.value = []
  pdfBytes = null
  selected.value = null
  if (props.status !== 'ready') return
  try {
    const bytes = await fetchClipPreview(props.lessonId)
    if (gen !== loadGen) return
    pdfBytes = bytes
    const pdfjs = await import('pdfjs-dist')
    const base = import.meta.env.BASE_URL.replace(/\/?$/, '/')
    pdfjs.GlobalWorkerOptions.workerSrc = `${base}pdf.worker.min.mjs`
    const pdf = await pdfjs.getDocument({ data: bytes.slice() }).promise
    const urls: string[] = []
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      if (gen !== loadGen) break
      const page = await pdf.getPage(pageNumber)
      const viewport = page.getViewport({ scale: 0.35 })
      const canvas = document.createElement('canvas')
      canvas.width = Math.floor(viewport.width)
      canvas.height = Math.floor(viewport.height)
      const context = canvas.getContext('2d')
      if (!context) continue
      await page.render({ canvas, canvasContext: context, viewport }).promise
      urls.push(canvas.toDataURL('image/jpeg', 0.82))
    }
    await pdf.cleanup()
    if (gen === loadGen) thumbs.value = urls
  } catch {
    if (gen === loadGen) thumbs.value = []
  }
}

async function openPage(index: number): Promise<void> {
  selected.value = index
  await nextPaint()
  const canvas = dialogCanvas.value
  if (!canvas) return
  await renderPage(index + 1, 1.15, canvas)
}

function nextPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => resolve())
  })
}

watch(
  () => [props.lessonId, props.status] as const,
  () => {
    void loadThumbs()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  loadGen += 1
})
</script>

<template>
  <aside class="clip-slides">
    <div class="clip-slides-head">
      <h2><I18nText k="clipTeaching.slidesTitle" /></h2>
      <label
        v-if="canEdit"
        class="clip-slides-upload"
      >
        <I18nText k="clipTeaching.uploadDeck" />
        <input
          type="file"
          accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
          :disabled="busy"
          @change="onFile"
        />
      </label>
    </div>
    <p
      v-if="status === 'pending'"
      class="clip-slides-note"
    >
      <I18nText k="clipTeaching.deckPending" />
    </p>
    <p
      v-else-if="status === 'failed'"
      class="clip-slides-note"
    >
      <I18nText k="clipTeaching.deckFailed" />
    </p>
    <p
      v-else-if="status === 'none'"
      class="clip-slides-note"
    >
      <I18nText k="clipTeaching.deckEmpty" />
    </p>
    <button
      v-for="(thumb, index) in thumbs"
      :key="`${lessonId}-${index}`"
      type="button"
      class="clip-slide"
      @click="openPage(index)"
    >
      <img
        :src="thumb"
        :alt="t('clipTeaching.slideN', { n: index + 1 })"
      />
    </button>
    <div
      v-if="selected != null"
      class="clip-slide-dialog"
      @click.self="selected = null"
    >
      <canvas ref="dialogCanvas" />
      <button
        type="button"
        @click="selected = null"
      >
        <I18nText k="clipTeaching.closeSlide" />
      </button>
    </div>
  </aside>
</template>

<style scoped>
.clip-slides {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: auto;
}

.clip-slides-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.clip-slides h2 {
  margin: 0;
  font-size: 14px;
}

.clip-slides-upload {
  font-size: 12px;
  cursor: pointer;
  color: #1c1917;
}

.clip-slides-upload input {
  display: none;
}

.clip-slides-note {
  margin: 0;
  color: #78716c;
  font-size: 13px;
}

.clip-slide {
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  padding: 0;
  background: #fff;
  cursor: pointer;
}

.clip-slide img {
  display: block;
  width: 100%;
  height: auto;
}

.clip-slide-dialog {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgba(28, 25, 23, 0.72);
}

.clip-slide-dialog canvas {
  max-width: min(920px, 92vw);
  max-height: 80vh;
  background: #fff;
}

.clip-slide-dialog button {
  border: 0;
  border-radius: 8px;
  background: #fff;
  padding: 8px 12px;
  cursor: pointer;
}
</style>
