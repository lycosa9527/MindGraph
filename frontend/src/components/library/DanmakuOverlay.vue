<script setup lang="ts">
/**
 * DanmakuOverlay - Overlay component for displaying danmaku and highlights
 * Uses vue-danmaku for animations and renders highlights on canvas
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useLibraryStore } from '@/stores/library'

interface Props {
  documentId: number
  currentPage: number | null
}

const props = defineProps<Props>()

const libraryStore = useLibraryStore()
const overlayRef = ref<HTMLElement | null>(null)
const highlightCanvasRef = ref<HTMLCanvasElement | null>(null)

// Fetch danmaku when page changes
watch(
  () => props.currentPage,
  async (newPage) => {
    if (newPage) {
      await libraryStore.fetchDanmaku(newPage)
      renderHighlights()
    }
  },
  { immediate: true }
)

// Render highlights on canvas
function renderHighlights() {
  if (!highlightCanvasRef.value || !props.currentPage) return

  const canvas = highlightCanvasRef.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Clear canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Get danmaku for current page with text selections
  const pageDanmaku = libraryStore.danmakuForPage(props.currentPage)
  const textSelectionDanmaku = pageDanmaku.filter((d) => d.selected_text && d.text_bbox)

  // Group by selected_text to count comments
  const highlights = new Map<string, { count: number; bbox: any; color: string }>()
  textSelectionDanmaku.forEach((d) => {
    if (d.selected_text && d.text_bbox) {
      const key = d.selected_text
      if (!highlights.has(key)) {
        highlights.set(key, {
          count: 0,
          bbox: d.text_bbox,
          color: d.highlight_color || '#fef08a',
        })
      }
      highlights.get(key)!.count++
    }
  })

  // Render highlights
  highlights.forEach((highlight) => {
    const { bbox, count, color } = highlight
    ctx.fillStyle = count > 1 ? '#fbbf24' : color
    ctx.globalAlpha = 0.3
    ctx.fillRect(bbox.x, bbox.y, bbox.width, bbox.height)
    ctx.globalAlpha = 1.0
  })
}

// Track if mouse is down to enable pointer events only during click
const isMouseDown = ref(false)

function handleCanvasMouseDown(event: MouseEvent) {
  isMouseDown.value = true
  if (highlightCanvasRef.value) {
    highlightCanvasRef.value.style.pointerEvents = 'auto'
  }
  handleCanvasClick(event)
}

function handleCanvasMouseUp() {
  isMouseDown.value = false
  // Small delay to allow click event to fire
  setTimeout(() => {
    if (highlightCanvasRef.value && !isMouseDown.value) {
      highlightCanvasRef.value.style.pointerEvents = 'none'
    }
  }, 10)
}

// Handle highlight click
function handleCanvasClick(event: MouseEvent) {
  if (!highlightCanvasRef.value || !props.currentPage) return

  const canvas = highlightCanvasRef.value
  const rect = canvas.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  // Find clicked highlight
  const pageDanmaku = libraryStore.danmakuForPage(props.currentPage)
  const clickedDanmaku = pageDanmaku.find((d) => {
    if (!d.text_bbox) return false
    const bbox = d.text_bbox
    return (
      x >= bbox.x &&
      x <= bbox.x + bbox.width &&
      y >= bbox.y &&
      y <= bbox.y + bbox.height
    )
  })

  if (clickedDanmaku && clickedDanmaku.selected_text) {
    libraryStore.selectedText = clickedDanmaku.selected_text
    libraryStore.fetchDanmaku(props.currentPage, clickedDanmaku.selected_text)
  }
}

// Update canvas size
function updateCanvasSize() {
  if (!highlightCanvasRef.value || !overlayRef.value) return

  const container = overlayRef.value
  highlightCanvasRef.value.width = container.clientWidth
  highlightCanvasRef.value.height = container.clientHeight
}

let danmakuWatcher: (() => void) | null = null

onMounted(() => {
  updateCanvasSize()
  window.addEventListener('resize', updateCanvasSize)
  danmakuWatcher = watch(() => libraryStore.danmaku, renderHighlights, { deep: true })
})

onUnmounted(() => {
  window.removeEventListener('resize', updateCanvasSize)
  if (danmakuWatcher) {
    danmakuWatcher()
    danmakuWatcher = null
  }
})
</script>

<template>
  <div
    ref="overlayRef"
    class="danmaku-overlay absolute inset-0 pointer-events-none"
  >
    <canvas
      ref="highlightCanvasRef"
      class="highlight-canvas absolute inset-0"
      @click="handleCanvasClick"
      @mousedown="handleCanvasMouseDown"
      @mouseup="handleCanvasMouseUp"
    />
  </div>
</template>

<style scoped>
.danmaku-overlay {
  z-index: 10;
}

.highlight-canvas {
  z-index: 11;
  /* Don't capture pointer events by default - let text layer handle cursor/selection */
  /* Only enable pointer events when clicking (handled by JS) */
  pointer-events: none;
  cursor: text;
}
</style>
