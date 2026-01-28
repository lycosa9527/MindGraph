<script setup lang="ts">
/**
 * PdfViewer - PDF viewer with page-flip animation
 * Uses pdfjs-dist for rendering and page-flip for animations
 */
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import { PageFlip } from 'page-flip'

// Set up PDF.js worker - use local copy instead of CDN
// Worker file is copied to public folder by Vite plugin during build/dev
if (typeof window !== 'undefined') {
  // Use worker from public folder (served by Vite, offline copy)
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js'
}

interface Props {
  pdfUrl: string
  documentId: number
}

interface Emits {
  (e: 'page-change', pageNumber: number): void
  (e: 'text-selection', text: string, bbox: { x: number; y: number; width: number; height: number }, pageNumber: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const containerRef = ref<HTMLElement | null>(null)
const pageFlipRef = ref<PageFlip | null>(null)
const pdfDocument = ref<any>(null)
const totalPages = ref(0)
const currentPage = ref(1)
const renderedPages = ref<Map<number, HTMLCanvasElement>>(new Map())
const loadingPages = ref<Set<number>>(new Set())

// Load PDF document
async function loadPdf() {
  try {
    const loadingTask = pdfjsLib.getDocument(props.pdfUrl)
    pdfDocument.value = await loadingTask.promise
    totalPages.value = pdfDocument.value.numPages

    // Pre-render first 2-3 pages
    await renderPages([1, 2, 3])

    // Initialize page-flip after initial pages are rendered
    await nextTick()
    initializePageFlip()
  } catch (error) {
    console.error('[PdfViewer] Failed to load PDF:', error)
  }
}

// Render specific pages with text layer support
async function renderPages(pageNumbers: number[]) {
  if (!pdfDocument.value) return

  for (const pageNum of pageNumbers) {
    if (renderedPages.value.has(pageNum) || loadingPages.value.has(pageNum)) {
      continue
    }

    loadingPages.value.add(pageNum)
    try {
      const page = await pdfDocument.value.getPage(pageNum)
      const viewport = page.getViewport({ scale: 2.0 })

      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      if (!context) continue

      canvas.height = viewport.height
      canvas.width = viewport.width

      // Render PDF page to canvas
      await page.render({
        canvasContext: context,
        viewport: viewport,
      }).promise

      // Enable text layer for text selection (for OCRed PDFs)
      try {
        const textContent = await page.getTextContent()
        // Text layer is now available for selection
        // PDF.js will handle text selection automatically if text layer is enabled
      } catch (textError) {
        console.debug(`[PdfViewer] Text layer not available for page ${pageNum} (may not be OCRed)`)
      }

      renderedPages.value.set(pageNum, canvas)
    } catch (error) {
      console.error(`[PdfViewer] Failed to render page ${pageNum}:`, error)
    } finally {
      loadingPages.value.delete(pageNum)
    }
  }
}

// Initialize page-flip
function initializePageFlip() {
  if (!containerRef.value) return

  const pageFlip = new PageFlip(containerRef.value, {
    width: 800,
    height: 1000,
    showCover: true,
    maxShadowOpacity: 0.5,
  })

  // Create pages for page-flip
  const pages: HTMLElement[] = []
  for (let i = 1; i <= totalPages.value; i++) {
    const pageDiv = document.createElement('div')
    pageDiv.className = 'page'
    pageDiv.dataset.pageNumber = i.toString()

    if (renderedPages.value.has(i)) {
      const canvas = renderedPages.value.get(i)!
      pageDiv.appendChild(canvas)
    } else {
      pageDiv.innerHTML = '<div class="loading-spinner">加载中...</div>'
    }

    pages.push(pageDiv)
  }

  pageFlip.loadFromHTML(pages)

  // Emit initial page change event (page 1)
  currentPage.value = 1
  emit('page-change', 1)

  // Handle page flip events
  pageFlip.on('flip', (e: any) => {
    const newPage = e.data + 1
    currentPage.value = newPage
    emit('page-change', newPage)

    // Pre-render adjacent pages
    const pagesToRender: number[] = []
    if (newPage > 1 && !renderedPages.value.has(newPage - 1)) {
      pagesToRender.push(newPage - 1)
    }
    if (newPage < totalPages.value && !renderedPages.value.has(newPage + 1)) {
      pagesToRender.push(newPage + 1)
    }
    if (pagesToRender.length > 0) {
      renderPages(pagesToRender).then(() => {
        // Update page-flip with rendered pages
        updatePageFlipPages()
      })
    }
  })

  pageFlipRef.value = pageFlip
}

// Update page-flip pages with rendered canvases
function updatePageFlipPages() {
  if (!pageFlipRef.value || !containerRef.value) return

  const pages = containerRef.value.querySelectorAll('.page')
  pages.forEach((pageEl, index) => {
    const pageNum = index + 1
    if (renderedPages.value.has(pageNum) && pageEl.querySelector('canvas') === null) {
      const canvas = renderedPages.value.get(pageNum)!
      pageEl.innerHTML = ''
      pageEl.appendChild(canvas)
    }
  })
}

// Handle text selection with PDF.js text layer support
async function handleTextSelection() {
  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0) return

  const selectedText = selection.toString().trim()
  if (!selectedText || selectedText.length < 3) return

  // Try to get bounding box from PDF.js text layer if available
  const range = selection.getRangeAt(0)
  const containerRect = containerRef.value?.getBoundingClientRect()
  if (!containerRect) return

  // Get bounding box relative to container
  const rect = range.getBoundingClientRect()
  const bbox = {
    x: rect.left - containerRect.left,
    y: rect.top - containerRect.top,
    width: rect.width,
    height: rect.height,
  }

  // Try to get more accurate coordinates from PDF.js text layer
  if (pdfDocument.value && currentPage.value) {
    try {
      const page = await pdfDocument.value.getPage(currentPage.value)
      const textContent = await page.getTextContent()
      
      // Find text items that match selection
      const textItems = textContent.items
      let startFound = false
      let endFound = false
      let startBbox: any = null
      let endBbox: any = null

      for (const item of textItems) {
        const itemText = (item as any).str
        if (!startFound && itemText.includes(selectedText.substring(0, Math.min(10, selectedText.length)))) {
          startFound = true
          startBbox = (item as any).transform
        }
        if (startFound && itemText.includes(selectedText.substring(Math.max(0, selectedText.length - 10)))) {
          endFound = true
          endBbox = (item as any).transform
          break
        }
      }

      // If we found text layer coordinates, use them
      if (startBbox && endBbox) {
        const viewport = page.getViewport({ scale: 2.0 })
        const x = Math.min(startBbox[4], endBbox[4])
        const y = Math.min(startBbox[5], endBbox[5])
        const width = Math.abs(endBbox[4] - startBbox[4])
        const height = Math.abs(endBbox[5] - startBbox[5])
        
        emit('text-selection', selectedText, {
          x: x / viewport.width * containerRect.width,
          y: (viewport.height - y) / viewport.height * containerRect.height,
          width: width / viewport.width * containerRect.width,
          height: height / viewport.height * containerRect.height,
        }, currentPage.value)
        return
      }
    } catch (error) {
      console.warn('[PdfViewer] Failed to get text layer coordinates:', error)
    }
  }

  // Fallback to DOM-based bounding box
  emit('text-selection', selectedText, bbox, currentPage.value)
}

onMounted(() => {
  loadPdf()
  // Use setTimeout to ensure PDF is loaded before attaching listeners
  setTimeout(() => {
    if (containerRef.value) {
      containerRef.value.addEventListener('mouseup', handleTextSelection)
      containerRef.value.addEventListener('touchend', handleTextSelection)
    }
  }, 1000)
})

onUnmounted(() => {
  if (containerRef.value) {
    containerRef.value.removeEventListener('mouseup', handleTextSelection)
    containerRef.value.removeEventListener('touchend', handleTextSelection)
  }
  if (pageFlipRef.value) {
    pageFlipRef.value.destroy()
  }
})

watch(() => props.pdfUrl, () => {
  loadPdf()
})
</script>

<template>
  <div
    ref="containerRef"
    class="pdf-viewer-container"
  />
</template>

<style scoped>
.pdf-viewer-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f5f4;
}

.pdf-viewer-container :deep(.page) {
  background: white;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.pdf-viewer-container :deep(.page canvas) {
  max-width: 100%;
  height: auto;
}

.loading-spinner {
  padding: 2rem;
  color: #78716c;
}
</style>
