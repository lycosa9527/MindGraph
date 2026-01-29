<script setup lang="ts">
/**
 * PdfViewer - Simple PDF viewer with pin-based comments
 * Uses pdfjs-dist for rendering
 * Users click on page to place pins, click pins to see comments
 */
import { ref, onMounted, onUnmounted, watch, markRaw, nextTick, createApp, h } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { ChatRound } from '@element-plus/icons-vue'
import { ElBadge, ElIcon, ElButton } from 'element-plus'
import ElementPlus from 'element-plus'
import { useLibraryStore } from '@/stores/library'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables'
import type { LibraryDanmaku } from '@/utils/apiClient'

// Set up PDF.js worker - use local copy from /pdfjs/ directory (served via StaticFiles mount)
if (typeof window !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdfjs/pdf.worker.min.js'
}

interface Props {
  pdfUrl: string
  documentId: number
  danmaku?: LibraryDanmaku[] // Danmaku for current page to show pins
}

interface Emits {
  (e: 'page-change', pageNumber: number): void
  (e: 'pin-place', x: number, y: number, pageNumber: number): void
  (e: 'pin-click', danmakuId: number): void
  (e: 'zoom-change', zoom: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const libraryStore = useLibraryStore()
const authStore = useAuthStore()
const notify = useNotifications()

const containerRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const pinsLayerRef = ref<HTMLElement | null>(null)
const pdfDocument = ref<any>(null)
const totalPages = ref(0)
const currentPage = ref(1)
const zoom = ref(1.0)
const rotation = ref(0)
const loading = ref(false)
const pinMode = ref(false) // Pin placement mode - must be enabled from toolbar
const temporaryPin = ref<{ x: number; y: number } | null>(null) // Temporary pin shown immediately on click

// Drag state
const draggingPin = ref<{ danmakuId: number; element: HTMLElement; startX: number; startY: number; initialX: number; initialY: number } | null>(null)

// Toggle pin mode
function togglePinMode() {
  pinMode.value = !pinMode.value
  updateCursor()
  // Clear temporary pin when disabling pin mode
  if (!pinMode.value) {
    temporaryPin.value = null
    // Only render pins if refs are available
    if (pinsLayerRef.value && canvasRef.value) {
      renderPins()
    }
  }
}

// Clear temporary pin (called from parent when comment panel closes)
function clearTemporaryPin() {
  temporaryPin.value = null
  // Only render pins if refs are available
  if (pinsLayerRef.value && canvasRef.value) {
    renderPins()
  }
}

// Update cursor based on pin mode - use custom pin cursor
function updateCursor() {
  if (!containerRef.value) return
  
  if (pinMode.value) {
    // Use custom pin cursor
    containerRef.value.style.cursor = 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'24\' height=\'24\' viewBox=\'0 0 24 24\'%3E%3Cpath d=\'M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z\' fill=\'%233b82f6\' stroke=\'white\' stroke-width=\'1.5\'/%3E%3Ccircle cx=\'12\' cy=\'10\' r=\'3\' fill=\'white\'/%3E%3C/svg%3E") 12 24, crosshair'
    if (canvasRef.value) {
      canvasRef.value.style.cursor = 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'24\' height=\'24\' viewBox=\'0 0 24 24\'%3E%3Cpath d=\'M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z\' fill=\'%233b82f6\' stroke=\'white\' stroke-width=\'1.5\'/%3E%3Ccircle cx=\'12\' cy=\'10\' r=\'3\' fill=\'white\'/%3E%3C/svg%3E") 12 24, crosshair'
    }
    const canvasWrapper = containerRef.value.querySelector('.pdf-canvas-wrapper')
    if (canvasWrapper instanceof HTMLElement) {
      canvasWrapper.style.cursor = 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'24\' height=\'24\' viewBox=\'0 0 24 24\'%3E%3Cpath d=\'M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z\' fill=\'%233b82f6\' stroke=\'white\' stroke-width=\'1.5\'/%3E%3Ccircle cx=\'12\' cy=\'10\' r=\'3\' fill=\'white\'/%3E%3C/svg%3E") 12 24, crosshair'
    }
  } else {
    containerRef.value.style.cursor = 'default'
    if (canvasRef.value) {
      canvasRef.value.style.cursor = 'default'
    }
    const canvasWrapper = containerRef.value.querySelector('.pdf-canvas-wrapper')
    if (canvasWrapper instanceof HTMLElement) {
      canvasWrapper.style.cursor = 'default'
    }
  }
}

// Expose methods and state for parent component
defineExpose({
  currentPage,
  totalPages,
  zoom,
  pinMode,
  goToPage: (page: number) => goToPage(page),
  zoomIn: () => adjustZoom(0.1),
  zoomOut: () => adjustZoom(-0.1),
  fitWidth: () => fitToWidth(),
  fitPage: () => fitToPage(),
  rotate: () => rotate(),
  download: () => downloadPdf(),
  print: () => printPdf(),
  togglePinMode: () => togglePinMode(),
  clearTemporaryPin: () => clearTemporaryPin(),
})

// Load PDF document
async function loadPdf() {
  try {
    loading.value = true
    console.log('[PdfViewer] Loading PDF from URL:', props.pdfUrl)
    
    const loadingTask = pdfjsLib.getDocument({
      url: props.pdfUrl,
      useSystemFonts: true,
      cMapUrl: '/cmaps/',
      cMapPacked: true,
    })
    
    const doc = await loadingTask.promise
    pdfDocument.value = markRaw(doc)
    totalPages.value = doc.numPages
    
    console.log('[PdfViewer] PDF loaded successfully:', { pages: totalPages.value })

    // Render first page
    await renderPage(1)
  } catch (error: any) {
    console.error('[PdfViewer] Failed to load PDF:', error)
    const errorMessage = error?.message || 'Failed to load PDF'
    notify.error(`PDF加载失败: ${errorMessage}`)
    
    // Log detailed error info for debugging
    if (error?.name) {
      console.error('[PdfViewer] Error name:', error.name)
    }
    if (error?.stack) {
      console.error('[PdfViewer] Error stack:', error.stack)
    }
  } finally {
    loading.value = false
  }
}

// Render current page
async function renderPage(pageNum: number) {
  if (!pdfDocument.value || pageNum < 1 || pageNum > totalPages.value) return

  await nextTick()
  
  let retries = 0
  const maxRetries = 10
  while ((!canvasRef.value || !pinsLayerRef.value) && retries < maxRetries) {
    await new Promise(resolve => setTimeout(resolve, 50))
    retries++
  }
  
  if (!canvasRef.value) {
    console.error('[PdfViewer] Canvas not available after retries')
    return
  }
  
  if (!pinsLayerRef.value) {
    console.error('[PdfViewer] Pins layer not available after retries')
    return
  }

  loading.value = true
  try {
    const page = await pdfDocument.value.getPage(pageNum)
    
    const containerRect = containerRef.value?.getBoundingClientRect()
    if (!containerRect) {
      console.warn('[PdfViewer] Container not available')
      return
    }
    
    const icpFooterHeight = 40
    const availableWidth = containerRect.width - 40
    const availableHeight = containerRect.height - 40 - icpFooterHeight
    
    const viewport = page.getViewport({ scale: 1.0, rotation: rotation.value })
    const scaleX = availableWidth / viewport.width
    const scaleY = availableHeight / viewport.height
    const adaptiveScale = Math.min(scaleX, scaleY, 3.0) * zoom.value
    
    const scaledViewport = page.getViewport({ scale: adaptiveScale, rotation: rotation.value })
    
    const canvas = canvasRef.value
    if (!canvas || !(canvas instanceof HTMLCanvasElement)) {
      console.error('[PdfViewer] Canvas element is null or invalid')
      return
    }
    
    if (!canvas.isConnected) {
      console.warn('[PdfViewer] Canvas not connected to DOM, waiting...')
      await nextTick()
      if (!canvas.isConnected) {
        console.error('[PdfViewer] Canvas still not connected after wait')
        return
      }
    }
    
    const context = canvas.getContext('2d')
    if (!context) {
      console.error('[PdfViewer] Failed to get 2d context')
      return
    }

    // Set canvas dimensions
    canvas.height = scaledViewport.height
    canvas.width = scaledViewport.width

    // Clear canvas
    context.clearRect(0, 0, canvas.width, canvas.height)

    // Render PDF page to canvas
    await page.render({
      canvasContext: context,
      viewport: scaledViewport,
    }).promise

    // Update pins layer after canvas is rendered
    await nextTick()
    // Small delay to ensure canvas position is stable
    // Check refs are still available before rendering pins
    setTimeout(() => {
      if (pinsLayerRef.value && canvasRef.value) {
        renderPins()
      } else {
        console.warn('[PdfViewer] Cannot render pins: refs not available in setTimeout', {
          hasPinsLayer: !!pinsLayerRef.value,
          hasCanvas: !!canvasRef.value
        })
      }
    }, 50)
    
    // Update cursor
    updateCursor()

    currentPage.value = pageNum
    emit('page-change', pageNum)
  } catch (error) {
    console.error(`[PdfViewer] Failed to render page ${pageNum}:`, error)
  } finally {
    loading.value = false
  }
}

// Store mounted Vue apps for cleanup
const mountedPinApps = new WeakMap<HTMLDivElement, ReturnType<typeof createApp>>()

// Check if user can drag a pin (owner or admin)
function canDragPin(danmaku: LibraryDanmaku): boolean {
  if (!authStore.user?.id) return false
  const userId = Number(authStore.user.id)
  const isOwner = userId === danmaku.user_id
  const isAdmin = authStore.isAdmin
  return isOwner || isAdmin
}

// Create a pin icon element using Element Plus Button, Icon, and Badge
function createPinIconElement(
  danmakuId: number | null = null, 
  isTemporary = false, 
  repliesCount: number = 0,
  danmaku?: LibraryDanmaku // Pass danmaku object to check drag permissions
): HTMLDivElement {
  const pinDiv = document.createElement('div')
  pinDiv.className = isTemporary ? 'pdf-pin-icon pdf-pin-temporary' : 'pdf-pin-icon'
  // CRITICAL: Explicitly set pointer-events to auto to override parent's pointer-events: none
  // This ensures pins are clickable and draggable
  pinDiv.style.pointerEvents = 'auto'
  if (danmakuId) {
    pinDiv.dataset.danmakuId = danmakuId.toString()
  }
  
  // Check if this pin can be dragged (for visual indication)
  const draggable = !isTemporary && danmaku && canDragPin(danmaku)
  if (draggable) {
    pinDiv.classList.add('pdf-pin-draggable')
    // Don't change cursor - left click should still show pointer for opening panel
  }
  
  // Calculate total comments (main comment + replies)
  const totalComments = repliesCount + 1
  
  // Create a Vue component: Badge wrapping Button with Icon
  const iconComponent = h(ElBadge, {
    value: !isTemporary && totalComments > 0 ? totalComments : 0,
    max: 99,
    hidden: isTemporary || totalComments === 0
  }, {
    default: () => h(ElButton, {
      type: 'primary',
      circle: true, // Circular button
      size: 'default',
      style: {
        width: '36px',
        height: '36px',
        padding: '0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, {
      default: () => h(ElIcon, {
        size: 20
      }, {
        default: () => h(ChatRound)
      })
    })
  })
  
  // Mount the Vue component to the div
  // Need to provide Element Plus to the dynamically created app
  try {
    const app = createApp({
      render: () => iconComponent
    })
    // Register Element Plus for the dynamic app
    app.use(ElementPlus)
    app.mount(pinDiv)
    
    // Store app reference for cleanup
    mountedPinApps.set(pinDiv, app)
    
    // Ensure pointer-events is still auto after Vue mounting (Vue might affect styles)
    nextTick(() => {
      pinDiv.style.pointerEvents = 'auto'
    })
  } catch (error) {
    console.error('[PdfViewer] Failed to mount pin icon:', error)
    // Fallback: create a simple div with text if Vue mounting fails
    pinDiv.textContent = '💬'
    pinDiv.style.display = 'flex'
    pinDiv.style.alignItems = 'center'
    pinDiv.style.justifyContent = 'center'
    pinDiv.style.backgroundColor = '#3b82f6'
    pinDiv.style.color = 'white'
    pinDiv.style.borderRadius = '50%'
    pinDiv.style.width = '36px'
    pinDiv.style.height = '36px'
    pinDiv.style.fontSize = '20px'
    // Ensure pointer-events is auto for fallback too
    pinDiv.style.pointerEvents = 'auto'
  }
  
  // Add click handler directly to pin element (in addition to delegation)
  // This ensures clicks work even if Element Plus components stop propagation
  if (danmakuId) {
    pinDiv.addEventListener('click', (e) => {
      // Don't handle if we're dragging
      if (draggingPin.value) {
        return
      }
      
      // Stop propagation to prevent canvas click handler
      e.stopPropagation()
      e.preventDefault()
      
      // Emit pin click event directly
      console.log('[PdfViewer] Pin clicked directly:', { danmakuId, pinElement: pinDiv })
      emit('pin-click', danmakuId)
    }, true) // Use capture phase to catch before Element Plus handlers
  }
  
  // Add drag event listeners for all pins (middle mouse button only)
  // We'll check permissions in handlePinDragStart
  // Attach drag handler if danmakuId exists, danmaku will be fetched if needed
  if (danmakuId) {
    pinDiv.addEventListener('mousedown', (e) => {
      // Only start drag on middle mouse button (button === 1)
      if (e.button === 1) {
        // Find danmaku from props if not passed directly
        const pinDanmaku = danmaku || (props.danmaku || []).find((d) => d.id === danmakuId)
        if (pinDanmaku) {
          handlePinDragStart(e, danmakuId, pinDiv, pinDanmaku)
        }
      }
    })
  }
  
  return pinDiv
}

// Render pin icons for danmaku on current page
function renderPins() {
  if (!pinsLayerRef.value || !canvasRef.value) {
    console.warn('[PdfViewer] Cannot render pins: missing refs', {
      hasPinsLayer: !!pinsLayerRef.value,
      hasCanvas: !!canvasRef.value
    })
    return
  }

  // Store refs in local constants for TypeScript control flow analysis
  const pinsLayer = pinsLayerRef.value
  const canvas = canvasRef.value

  // Clear existing pins and unmount Vue apps
  const existingPins = pinsLayer.querySelectorAll('.pdf-pin-icon')
  existingPins.forEach((pin) => {
    const app = mountedPinApps.get(pin as HTMLDivElement)
    if (app) {
      app.unmount()
      mountedPinApps.delete(pin as HTMLDivElement)
    }
  })
  pinsLayer.innerHTML = ''

  // Get canvas dimensions (intrinsic size from width/height attributes)
  const canvasIntrinsicWidth = canvas.width
  const canvasIntrinsicHeight = canvas.height
  
  // Validate canvas has valid dimensions
  if (canvasIntrinsicWidth === 0 || canvasIntrinsicHeight === 0) {
    console.warn('[PdfViewer] Canvas has zero dimensions, skipping pin render', {
      width: canvasIntrinsicWidth,
      height: canvasIntrinsicHeight
    })
    return
  }
  
  // Get canvas rendered size (actual displayed size, may be scaled by CSS)
  const canvasRect = canvas.getBoundingClientRect()
  const canvasRenderedWidth = canvasRect.width
  const canvasRenderedHeight = canvasRect.height
  
  // Validate rendered size
  if (canvasRenderedWidth === 0 || canvasRenderedHeight === 0) {
    console.warn('[PdfViewer] Canvas rendered size is zero, skipping pin render', {
      width: canvasRenderedWidth,
      height: canvasRenderedHeight
    })
    return
  }
  
  // Calculate scale factors (how much CSS scaled the canvas)
  const scaleX = canvasRenderedWidth / canvasIntrinsicWidth
  const scaleY = canvasRenderedHeight / canvasIntrinsicHeight
  
  // Validate scale factors
  if (!isFinite(scaleX) || !isFinite(scaleY) || scaleX <= 0 || scaleY <= 0) {
    console.error('[PdfViewer] Invalid scale factors', { scaleX, scaleY })
    return
  }
  
  // Set pins layer to match canvas's rendered size exactly
  // Both canvas and pins layer are children of canvas-wrapper
  // Canvas is display:block, pins layer is position:absolute
  // They should both start at (0,0) relative to wrapper
  pinsLayer.style.width = `${canvasRenderedWidth}px`
  pinsLayer.style.height = `${canvasRenderedHeight}px`
  pinsLayer.style.left = '0'
  pinsLayer.style.top = '0'
  pinsLayer.style.position = 'absolute' // Ensure absolute positioning
  
  // Debug: Check actual positions
  const wrapper = pinsLayer.parentElement
  const wrapperRect = wrapper?.getBoundingClientRect()
  const pinsLayerRect = pinsLayer.getBoundingClientRect()
  
  console.log('[PdfViewer] Pins layer positioned:', {
    canvasIntrinsic: { width: canvasIntrinsicWidth, height: canvasIntrinsicHeight },
    canvasRendered: { width: canvasRenderedWidth, height: canvasRenderedHeight },
    canvasRect: { left: canvasRect.left, top: canvasRect.top, width: canvasRect.width, height: canvasRect.height },
    wrapperRect: wrapperRect ? { left: wrapperRect.left, top: wrapperRect.top, width: wrapperRect.width, height: wrapperRect.height } : null,
    pinsLayerRect: { left: pinsLayerRect.left, top: pinsLayerRect.top, width: pinsLayerRect.width, height: pinsLayerRect.height },
    pinsLayerStyle: { 
      width: pinsLayer.style.width, 
      height: pinsLayer.style.height,
      left: pinsLayer.style.left,
      top: pinsLayer.style.top
    },
    scale: { x: scaleX, y: scaleY },
    offset: wrapperRect ? {
      canvasFromWrapper: { x: canvasRect.left - wrapperRect.left, y: canvasRect.top - wrapperRect.top },
      pinsFromWrapper: { x: pinsLayerRect.left - wrapperRect.left, y: pinsLayerRect.top - wrapperRect.top }
    } : null
  })

  // Render temporary pin if exists (only if no comment created yet at this position)
  // Store in local variable to prevent race conditions with watchers
  const currentTemporaryPin = temporaryPin.value
  if (currentTemporaryPin) {
    // Check if there's already a danmaku at this position (comment was created)
    const hasCommentAtPosition = (props.danmaku || []).some((d) => 
      d.page_number === currentPage.value &&
      d.position_x !== null &&
      d.position_y !== null &&
      Math.abs(d.position_x - currentTemporaryPin.x) < 5 &&
      Math.abs(d.position_y - currentTemporaryPin.y) < 5
    )
    
    // Only show temporary pin if no comment exists at this position
    if (!hasCommentAtPosition) {
      const tempPin = createPinIconElement(null, true, 0)
      // Scale temporary pin position to match rendered canvas size
      const tempScaledX = currentTemporaryPin.x * scaleX
      const tempScaledY = currentTemporaryPin.y * scaleY
      tempPin.style.left = `${tempScaledX}px`
      tempPin.style.top = `${tempScaledY}px`
      tempPin.style.position = 'absolute' // Ensure absolute positioning
      pinsLayer.appendChild(tempPin)
      
      console.log('[PdfViewer] Temporary pin positioned:', {
        tempPinPosition: currentTemporaryPin,
        scaledPosition: { x: tempScaledX, y: tempScaledY },
        pinStyle: { left: tempPin.style.left, top: tempPin.style.top }
      })
    } else {
      // Comment was created, clear temporary pin
      temporaryPin.value = null
    }
  }

  // Filter danmaku for current page with position coordinates
  const pageDanmaku = (props.danmaku || []).filter(
    (d) => d.page_number === currentPage.value && d.position_x !== null && d.position_y !== null
  )

  console.log('[PdfViewer] Rendering pins:', {
    totalDanmaku: props.danmaku?.length || 0,
    pageDanmaku: pageDanmaku.length,
    currentPage: currentPage.value,
    temporaryPin: temporaryPin.value,
    canvasIntrinsic: { width: canvasIntrinsicWidth, height: canvasIntrinsicHeight },
    canvasRendered: { width: canvasRenderedWidth, height: canvasRenderedHeight },
    scale: { x: scaleX, y: scaleY }
  })

  // Create pin icons for existing danmaku
  pageDanmaku.forEach((danmaku) => {
    if (danmaku.position_x === null || danmaku.position_y === null) return

    const repliesCount = danmaku.replies_count || 0
    // Always pass danmaku object to ensure handlers are attached correctly
    const pinDiv = createPinIconElement(danmaku.id, false, repliesCount, danmaku)
    
    // Validate stored position is within canvas bounds
    // Clamp invalid positions (e.g., negative values from old bugs) to valid range
    let validX = danmaku.position_x
    let validY = danmaku.position_y
    
    // Force clamp to valid range - handle negative or out-of-bounds positions
    if (validX < 0 || validX > canvasIntrinsicWidth || !isFinite(validX)) {
      console.warn('[PdfViewer] Invalid X position:', { original: validX, canvasWidth: canvasIntrinsicWidth })
      validX = Math.max(0, Math.min(validX || 0, canvasIntrinsicWidth))
    }
    if (validY < 0 || validY > canvasIntrinsicHeight || !isFinite(validY)) {
      console.warn('[PdfViewer] Invalid Y position:', { original: validY, canvasHeight: canvasIntrinsicHeight })
      validY = Math.max(0, Math.min(validY || 0, canvasIntrinsicHeight))
    }
    
    // Ensure values are numbers
    validX = Number(validX) || 0
    validY = Number(validY) || 0
    
    // Scale pin position to match rendered canvas size
    // position_x/y are stored relative to canvas intrinsic size, need to scale to rendered size
    const scaledX = validX * scaleX
    const scaledY = validY * scaleY
    
    // Clamp scaled position to pins layer bounds (ensure it's visible)
    const clampedScaledX = Math.max(0, Math.min(scaledX, canvasRenderedWidth))
    const clampedScaledY = Math.max(0, Math.min(scaledY, canvasRenderedHeight))
    
    // Warn if position was invalid
    if (danmaku.position_x !== validX || danmaku.position_y !== validY) {
      console.warn('[PdfViewer] Invalid pin position clamped:', {
        danmakuId: danmaku.id,
        original: { x: danmaku.position_x, y: danmaku.position_y },
        clamped: { x: validX, y: validY },
        canvasIntrinsic: { width: canvasIntrinsicWidth, height: canvasIntrinsicHeight }
      })
    }
    
    // Set position explicitly - pin icon has margin-left: -18px and margin-top: -18px
    // to center the pin tip at the click point
    // Use clamped values to ensure pin is visible
    pinDiv.style.left = `${clampedScaledX}px`
    pinDiv.style.top = `${clampedScaledY}px`
    pinDiv.style.position = 'absolute' // Ensure absolute positioning
    
    // Force style application by reading back immediately
    const computedLeft = window.getComputedStyle(pinDiv).left
    const computedTop = window.getComputedStyle(pinDiv).top
    
    // Verify the style was actually applied
    const actualLeft = parseFloat(pinDiv.style.left) || 0
    const actualTop = parseFloat(pinDiv.style.top) || 0
    
    console.log('[PdfViewer] Creating pin:', {
      danmakuId: danmaku.id,
      repliesCount,
      totalComments: repliesCount + 1,
      storedPosition: { x: danmaku.position_x, y: danmaku.position_y },
      validPosition: { x: validX, y: validY },
      scale: { x: scaleX, y: scaleY },
      scaledPosition: { x: scaledX, y: scaledY },
      clampedScaledPosition: { x: clampedScaledX, y: clampedScaledY },
      pinStyle: { left: pinDiv.style.left, top: pinDiv.style.top, position: pinDiv.style.position },
      actualPosition: { left: actualLeft, top: actualTop },
      computedStyle: { left: computedLeft, top: computedTop },
      pinsLayerSize: { width: pinsLayer.style.width, height: pinsLayer.style.height },
      pinsLayerPosition: { left: pinsLayer.style.left, top: pinsLayer.style.top }
    })
    
    // Double-check: if position is still invalid, force it to (0, 0)
    if (actualLeft < 0 || actualTop < 0 || !isFinite(actualLeft) || !isFinite(actualTop)) {
      console.error('[PdfViewer] Pin position still invalid after clamping, forcing to (0,0):', {
        danmakuId: danmaku.id,
        actualLeft,
        actualTop
      })
      pinDiv.style.left = '0px'
      pinDiv.style.top = '0px'
    }
    
    pinsLayer.appendChild(pinDiv)
    
    // CRITICAL: Ensure pointer-events is auto after appending to DOM
    // This overrides any parent styles that might affect it
    pinDiv.style.pointerEvents = 'auto'
    
    // After appending, verify actual position and fix if needed
    nextTick().then(() => {
      // Double-check pointer-events is still auto
      pinDiv.style.pointerEvents = 'auto'
      const pinRect = pinDiv.getBoundingClientRect()
      const pinsLayerRect = pinsLayerRef.value?.getBoundingClientRect()
      const relativeX = pinsLayerRect ? pinRect.left - pinsLayerRect.left : 0
      const relativeY = pinsLayerRect ? pinRect.top - pinsLayerRect.top : 0
      
      // If pin is still off-screen or invalid, force it to visible position
      const isOffScreen = !pinsLayerRect || relativeX < -50 || relativeY < -50 || 
          relativeX > pinsLayerRect.width + 50 || relativeY > pinsLayerRect.height + 50 ||
          !isFinite(relativeX) || !isFinite(relativeY)
      
      if (isOffScreen) {
        console.error('[PdfViewer] Pin is off-screen after append, forcing to visible position:', {
          danmakuId: danmaku.id,
          relativeX,
          relativeY,
          pinsLayerRect: pinsLayerRect ? { width: pinsLayerRect.width, height: pinsLayerRect.height } : null,
          currentStyle: { left: pinDiv.style.left, top: pinDiv.style.top }
        })
        // Force pin to center of visible area
        const forcedX = Math.max(50, Math.min(canvasRenderedWidth - 50, clampedScaledX || 50))
        const forcedY = Math.max(50, Math.min(canvasRenderedHeight - 50, clampedScaledY || 50))
        pinDiv.style.left = `${forcedX}px`
        pinDiv.style.top = `${forcedY}px`
        
        // Verify it was set
        console.log('[PdfViewer] Pin position forced to:', {
          forcedX,
          forcedY,
          newStyle: { left: pinDiv.style.left, top: pinDiv.style.top }
        })
      }
      
      console.log('[PdfViewer] Pin actual position after append:', {
        danmakuId: danmaku.id,
        pinRect: { left: pinRect.left, top: pinRect.top, width: pinRect.width, height: pinRect.height },
        pinsLayerRect: pinsLayerRect ? { left: pinsLayerRect.left, top: pinsLayerRect.top, width: pinsLayerRect.width, height: pinsLayerRect.height } : null,
        relativeToPinsLayer: { x: relativeX, y: relativeY },
        isVisible: !isOffScreen,
        pinElement: pinDiv,
        hasPointerEvents: window.getComputedStyle(pinDiv).pointerEvents
      })
    })
  })
  
  console.log('[PdfViewer] Pins rendered:', {
    pinsCreated: pageDanmaku.length,
    temporaryPin: temporaryPin.value !== null,
    pinsLayerChildren: pinsLayer.children.length
  })
}

// Handle canvas click to place pin (only when pin mode is active)
function handleCanvasClick(event: MouseEvent) {
  if (!pinMode.value) return // Only allow pin placement when pin mode is active
  if (!canvasRef.value || !pinsLayerRef.value) return

  // Don't handle clicks on pins (they have their own handler)
  const target = event.target as HTMLElement
  if (target.closest('.pdf-pin-icon')) {
    return
  }

  // Get canvas dimensions
  const canvasIntrinsicWidth = canvasRef.value.width
  const canvasIntrinsicHeight = canvasRef.value.height
  
  // Get click position relative to rendered canvas
  const canvasRect = canvasRef.value.getBoundingClientRect()
  const clickX = event.clientX - canvasRect.left
  const clickY = event.clientY - canvasRect.top
  
  // Validate click is actually on the canvas (not on wrapper padding/margin)
  if (clickX < 0 || clickY < 0 || clickX > canvasRect.width || clickY > canvasRect.height) {
    console.warn('[PdfViewer] Click outside canvas bounds (rendered):', { 
      clickPos: { x: clickX, y: clickY },
      canvasRendered: { width: canvasRect.width, height: canvasRect.height }
    })
    return
  }
  
  // Calculate scale factors (how much CSS scaled the canvas)
  const scaleX = canvasRect.width / canvasIntrinsicWidth
  const scaleY = canvasRect.height / canvasIntrinsicHeight
  
  // Validate scale factors
  if (!isFinite(scaleX) || !isFinite(scaleY) || scaleX <= 0 || scaleY <= 0) {
    console.error('[PdfViewer] Invalid scale factors:', { scaleX, scaleY })
    return
  }
  
  // Convert click coordinates from rendered size to intrinsic size
  // This is what we store in the database (relative to canvas width/height attributes)
  const x = clickX / scaleX
  const y = clickY / scaleY

  // Ensure coordinates are within canvas bounds (intrinsic size)
  // Clamp to valid range instead of rejecting
  const clampedX = Math.max(0, Math.min(x, canvasIntrinsicWidth))
  const clampedY = Math.max(0, Math.min(y, canvasIntrinsicHeight))
  
  if (x !== clampedX || y !== clampedY) {
    console.warn('[PdfViewer] Click coordinates clamped:', { 
      original: { x, y },
      clamped: { x: clampedX, y: clampedY },
      canvasIntrinsic: { width: canvasIntrinsicWidth, height: canvasIntrinsicHeight }
    })
  }
  
  // Use clamped coordinates
  const finalX = clampedX
  const finalY = clampedY

  console.log('[PdfViewer] Pin placed:', {
    clickPos: { clientX: event.clientX, clientY: event.clientY },
    clickRelativeToRendered: { x: clickX, y: clickY },
    canvasRect: { left: canvasRect.left, top: canvasRect.top, width: canvasRect.width, height: canvasRect.height },
    intrinsicPos: { x: finalX, y: finalY }, // This is what gets stored in DB - relative to canvas intrinsic size
    canvasIntrinsic: { width: canvasIntrinsicWidth, height: canvasIntrinsicHeight },
    canvasRendered: { width: canvasRect.width, height: canvasRect.height },
    scale: { x: scaleX, y: scaleY },
    note: 'Stored coordinates are relative to canvas intrinsic size, will be scaled when rendering'
  })

  // Show temporary pin icon immediately (use intrinsic coordinates)
  temporaryPin.value = { x: finalX, y: finalY }
  
  // Emit pin placement event with intrinsic coordinates (what we store in DB)
  emit('pin-place', finalX, finalY, currentPage.value)
  
  // Disable pin mode after placing pin
  pinMode.value = false
  updateCursor()
}

// Handle pin drag start (middle mouse button only)
function handlePinDragStart(event: MouseEvent, danmakuId: number, pinElement: HTMLElement, danmaku?: LibraryDanmaku) {
  // Only allow middle mouse button (button === 1) for dragging
  if (event.button !== 1) {
    return
  }
  
  // Check if user can drag this pin
  if (!danmaku || !canDragPin(danmaku)) {
    event.preventDefault()
    event.stopPropagation()
    notify.warning('只能移动自己的评论')
    return
  }
  
  // Don't start drag if clicking on badge
  const target = event.target as HTMLElement
  const badge = target.closest('.el-badge__content')
  if (badge) {
    return // Clicking on badge, don't drag
  }
  
  // Prevent default middle mouse button behavior (scrolling, auto-scroll)
  event.preventDefault()
  event.stopPropagation()
  
  // Get current position
  const rect = pinElement.getBoundingClientRect()
  const pinsLayerRect = pinsLayerRef.value?.getBoundingClientRect()
  if (!pinsLayerRect) return
  
  const currentX = rect.left - pinsLayerRect.left
  const currentY = rect.top - pinsLayerRect.top
  
  draggingPin.value = {
    danmakuId,
    element: pinElement,
    startX: event.clientX,
    startY: event.clientY,
    initialX: currentX,
    initialY: currentY
  }
  
  pinElement.style.zIndex = '25' // Bring to front while dragging
  pinElement.style.opacity = '0.8'
  
  // Add global mouse move and up listeners
  document.addEventListener('mousemove', handlePinDrag)
  document.addEventListener('mouseup', handlePinDragEnd)
  
  // Prevent context menu during drag
  const preventContextMenu = (e: Event) => {
    if (draggingPin.value) {
      e.preventDefault()
    }
  }
  document.addEventListener('contextmenu', preventContextMenu)
  
  // Store cleanup function
  ;(pinElement as any)._dragCleanup = () => {
    document.removeEventListener('contextmenu', preventContextMenu)
  }
}

// Handle pin drag
function handlePinDrag(event: MouseEvent) {
  if (!draggingPin.value || !pinsLayerRef.value) return
  
  const { element, startX, startY, initialX, initialY } = draggingPin.value
  const pinsLayerRect = pinsLayerRef.value.getBoundingClientRect()
  
  // Calculate new position relative to pins layer
  const deltaX = event.clientX - startX
  const deltaY = event.clientY - startY
  
  const newX = initialX + deltaX
  const newY = initialY + deltaY
  
  // Constrain to pins layer bounds
  const pinsLayerWidth = parseFloat(pinsLayerRef.value.style.width) || 0
  const pinsLayerHeight = parseFloat(pinsLayerRef.value.style.height) || 0
  const constrainedX = Math.max(0, Math.min(newX, pinsLayerWidth))
  const constrainedY = Math.max(0, Math.min(newY, pinsLayerHeight))
  
  element.style.left = `${constrainedX}px`
  element.style.top = `${constrainedY}px`
}

// Handle pin drag end
async function handlePinDragEnd(event: MouseEvent) {
  if (!draggingPin.value || !canvasRef.value || !pinsLayerRef.value) return
  
  const { danmakuId, element } = draggingPin.value
  
  // Clean up context menu prevention
  if ((element as any)._dragCleanup) {
    ;(element as any)._dragCleanup()
    delete (element as any)._dragCleanup
  }
  
  // Remove drag state
  element.style.zIndex = '21' // Return to normal pin z-index
  element.style.opacity = '1'
  
  // Remove global listeners
  document.removeEventListener('mousemove', handlePinDrag)
  document.removeEventListener('mouseup', handlePinDragEnd)
  
  // Get final position
  const pinsLayerRect = pinsLayerRef.value.getBoundingClientRect()
  const elementRect = element.getBoundingClientRect()
  const finalX = elementRect.left - pinsLayerRect.left
  const finalY = elementRect.top - pinsLayerRect.top
  
  // Convert from rendered coordinates to intrinsic coordinates
  const canvasIntrinsicWidth = canvasRef.value.width
  const canvasIntrinsicHeight = canvasRef.value.height
  const canvasRect = canvasRef.value.getBoundingClientRect()
  const scaleX = canvasRect.width / canvasIntrinsicWidth
  const scaleY = canvasRect.height / canvasIntrinsicHeight
  
  const intrinsicX = Math.round(finalX / scaleX)
  const intrinsicY = Math.round(finalY / scaleY)
  
  // Update position in database
  try {
    await libraryStore.updateDanmakuPosition(danmakuId, {
      position_x: intrinsicX,
      position_y: intrinsicY
    })
    notify.success('位置已更新')
    
    // Refresh danmaku to get updated position
    if (currentPage.value) {
      await libraryStore.fetchDanmaku(currentPage.value)
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '更新位置失败'
    notify.error(errorMessage)
    console.error('[PdfViewer] Failed to update pin position:', error)
    
    // Revert position on error
    if (pinsLayerRef.value && canvasRef.value) {
      renderPins()
    }
  }
  
  draggingPin.value = null
}

// Handle pin icon click (left click only)
function handlePinClick(event: MouseEvent) {
  console.log('[PdfViewer] handlePinClick called:', {
    eventType: event.type,
    button: event.button,
    draggingPin: !!draggingPin.value,
    target: (event.target as HTMLElement)?.tagName
  })
  
  // Don't handle click if we're dragging
  if (draggingPin.value) {
    console.log('[PdfViewer] Ignoring click - currently dragging')
    event.stopPropagation()
    return
  }
  
  // For click events, button property is usually 0 or undefined
  // Only filter out middle mouse button if this is a mousedown event
  if (event.type === 'mousedown' && event.button === 1) {
    console.log('[PdfViewer] Ignoring middle mouse button')
    return
  }
  
  event.stopPropagation() // Prevent triggering canvas click
  event.preventDefault() // Prevent default behavior
  
  const target = event.target as HTMLElement
  const pinElement = target.closest('.pdf-pin-icon') as HTMLElement
  if (!pinElement) {
    console.warn('[PdfViewer] Pin click handler called but no pin element found', {
      target: target.tagName,
      targetClasses: target.className
    })
    return
  }

  const danmakuId = parseInt(pinElement.dataset.danmakuId || '0')
  if (danmakuId > 0) {
    console.log('[PdfViewer] Pin clicked successfully:', { danmakuId, pinElement })
    emit('pin-click', danmakuId)
  } else {
    console.warn('[PdfViewer] Pin clicked but danmakuId is invalid:', { 
      danmakuId, 
      pinElement,
      dataset: pinElement.dataset
    })
  }
}

// Pin click handler wrapper for event delegation
function handlePinClickDelegation(e: Event) {
  if (!(e instanceof MouseEvent)) return
  
  const target = e.target as HTMLElement
  const pinElement = target.closest('.pdf-pin-icon') as HTMLElement
  
  if (pinElement) {
    // Click events don't have a button property - only mousedown events do
    // For click events, we check the event type and don't filter by button
    // Middle mouse button clicks are handled separately via mousedown
    console.log('[PdfViewer] Pin click delegation triggered:', {
      eventType: e.type,
      target: target.tagName,
      pinElement: !!pinElement,
      danmakuId: pinElement.dataset.danmakuId
    })
    handlePinClick(e)
  }
}

// Navigation functions
function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  renderPage(page)
}

function goToNextPage() {
  if (currentPage.value < totalPages.value) {
    renderPage(currentPage.value + 1)
  }
}

function goToPreviousPage() {
  if (currentPage.value > 1) {
    renderPage(currentPage.value - 1)
  }
}

// Zoom functions
function adjustZoom(delta: number) {
  const newZoom = Math.max(0.5, Math.min(3.0, zoom.value + delta))
  zoom.value = newZoom
  emit('zoom-change', newZoom)
  renderPage(currentPage.value)
}

function fitToWidth() {
  if (!containerRef.value || !pdfDocument.value) return
  const containerWidth = containerRef.value.clientWidth
  const estimatedPageWidth = 595
  const newZoom = (containerWidth - 40) / estimatedPageWidth
  zoom.value = Math.max(0.5, Math.min(3.0, newZoom))
  emit('zoom-change', zoom.value)
  renderPage(currentPage.value)
}

function fitToPage() {
  if (!containerRef.value || !pdfDocument.value) return
  const containerWidth = containerRef.value.clientWidth
  const containerHeight = containerRef.value.clientHeight
  const icpFooterHeight = 40
  const estimatedPageWidth = 595
  const estimatedPageHeight = 842
  const zoomWidth = (containerWidth - 40) / estimatedPageWidth
  const zoomHeight = (containerHeight - 40 - icpFooterHeight) / estimatedPageHeight
  const newZoom = Math.min(zoomWidth, zoomHeight)
  zoom.value = Math.max(0.5, Math.min(3.0, newZoom))
  emit('zoom-change', zoom.value)
  renderPage(currentPage.value)
}

// Rotate function
function rotate() {
  rotation.value = (rotation.value + 90) % 360
  renderPage(currentPage.value)
}

// Download function
function downloadPdf() {
  if (!props.pdfUrl) return
  const link = document.createElement('a')
  link.href = props.pdfUrl
  link.download = `document-${props.documentId}.pdf`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Print function
function printPdf() {
  if (!props.pdfUrl) return
  window.open(props.pdfUrl, '_blank')
}

// Handle window resize
let resizeTimeout: number | null = null
function handleResize() {
  if (resizeTimeout) {
    clearTimeout(resizeTimeout)
  }
  resizeTimeout = window.setTimeout(() => {
    if (currentPage.value) {
      renderPage(currentPage.value)
    }
  }, 250)
}

onMounted(async () => {
  await nextTick()
  
  let retries = 0
  const maxRetries = 20
  // Wait for all refs including pinsLayerRef before proceeding
  while ((!containerRef.value || !canvasRef.value || !pinsLayerRef.value) && retries < maxRetries) {
    await new Promise(resolve => setTimeout(resolve, 50))
    retries++
  }
  
  // Set up click handler for placing pins directly on canvas
  // This ensures coordinates are always relative to the canvas
  if (canvasRef.value) {
    canvasRef.value.addEventListener('click', handleCanvasClick)
  }
  
  // Set up pin click handler using event delegation on container
  // This works even when pins are dynamically added/removed
  // Use capture phase to ensure we catch clicks before other handlers
  if (containerRef.value) {
    containerRef.value.addEventListener('click', handlePinClickDelegation, true)
    console.log('[PdfViewer] Pin click handler attached to container (capture phase)')
  }
  
  // Only load PDF if all required refs are available
  if (canvasRef.value && pinsLayerRef.value) {
    loadPdf()
  } else {
    console.error('[PdfViewer] Required refs not available on mount', {
      hasCanvas: !!canvasRef.value,
      hasPinsLayer: !!pinsLayerRef.value,
      hasContainer: !!containerRef.value
    })
  }
  
  // Initialize cursor
  updateCursor()
  
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  // Remove canvas click handler
  if (canvasRef.value) {
    canvasRef.value.removeEventListener('click', handleCanvasClick)
  }
  
  if (containerRef.value) {
    // Remove pin click handler (event delegation) - must match capture phase
    containerRef.value.removeEventListener('click', handlePinClickDelegation, true)
  }
  
  // Clean up drag listeners
  document.removeEventListener('mousemove', handlePinDrag)
  document.removeEventListener('mouseup', handlePinDragEnd)
  
  if (resizeTimeout) {
    clearTimeout(resizeTimeout)
  }
  window.removeEventListener('resize', handleResize)
})

watch(() => props.pdfUrl, async () => {
  if (!props.pdfUrl) return
  
  await nextTick()
  let retries = 0
  const maxRetries = 20
  // Wait for all refs including pinsLayerRef
  while ((!containerRef.value || !canvasRef.value || !pinsLayerRef.value) && retries < maxRetries) {
    await new Promise(resolve => setTimeout(resolve, 50))
    retries++
  }
  
  if (canvasRef.value && pinsLayerRef.value) {
    loadPdf()
  } else {
    console.error('[PdfViewer] Required refs not available when pdfUrl changed', {
      hasCanvas: !!canvasRef.value,
      hasPinsLayer: !!pinsLayerRef.value
    })
  }
})

watch(() => props.danmaku, () => {
  // Only render pins if refs are available
  if (pinsLayerRef.value && canvasRef.value) {
    renderPins()
  }
}, { deep: true })

watch(currentPage, () => {
  // Clear temporary pin when page changes
  temporaryPin.value = null
  // Only render pins if refs are available
  if (pinsLayerRef.value && canvasRef.value) {
    renderPins()
  }
})

watch(pinMode, () => {
  updateCursor()
  // Clear temporary pin when pin mode is disabled
  if (!pinMode.value) {
    temporaryPin.value = null
    // Only render pins if refs are available
    if (pinsLayerRef.value && canvasRef.value) {
      renderPins()
    }
  }
})

watch(temporaryPin, () => {
  // Only render pins if refs are available
  if (pinsLayerRef.value && canvasRef.value) {
    renderPins()
  }
})
</script>

<template>
  <div class="pdf-viewer-wrapper relative">
    <div
      ref="containerRef"
      class="pdf-viewer-container"
    >
      <div class="pdf-canvas-wrapper">
        <canvas
          ref="canvasRef"
          class="pdf-canvas"
        />
        <!-- Pins layer for danmaku pin icons - always rendered -->
        <div
          ref="pinsLayerRef"
          class="pdf-pins-layer"
        />
      </div>
      <div
        v-if="loading"
        class="loading-spinner"
      >
        加载中...
      </div>
    </div>
    <!-- Floating Navigation Buttons -->
    <div
      v-if="totalPages > 0"
      class="pdf-nav-buttons"
    >
      <button
        v-if="currentPage > 1"
        class="nav-button-floating nav-button-prev"
        title="上一页"
        type="button"
        @click.stop="goToPreviousPage"
      >
        <ChevronLeft class="w-6 h-6" />
      </button>
      <button
        v-if="currentPage < totalPages"
        class="nav-button-floating nav-button-next"
        title="下一页"
        type="button"
        @click.stop="goToNextPage"
      >
        <ChevronRight class="w-6 h-6" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.pdf-viewer-wrapper {
  width: 100%;
  height: 100%;
}

.pdf-viewer-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f5f4;
  overflow: auto;
  position: relative;
  cursor: default;
}

.pdf-canvas-wrapper {
  position: relative;
  display: inline-block;
  cursor: default;
}

.pdf-canvas {
  max-width: 100%;
  max-height: 100%;
  display: block;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1;
  cursor: default;
  user-select: none;
  touch-action: none;
}

.pdf-pins-layer {
  position: absolute;
  /* Position will be set by JavaScript to match canvas */
  overflow: visible;
  /* Don't block clicks to canvas - only pin icons capture clicks */
  pointer-events: none;
  /* Ensure pins are above canvas and danmaku overlay (z-index 10-11) */
  z-index: 20;
}

.pdf-pin-icon {
  position: absolute;
  cursor: pointer;
  transition: all 0.2s ease;
  /* Pin icons capture clicks for opening comment panel */
  /* CRITICAL: pointer-events must be auto to override parent's pointer-events: none */
  /* Also set inline in JS to ensure it works */
  pointer-events: auto !important;
  /* Ensure pins are above pins layer and visible */
  z-index: 21;
  margin-left: -18px; /* Center the 36px button */
  margin-top: -18px;
}

.pdf-pin-draggable {
  cursor: pointer; /* Default cursor - left click opens panel */
}

/* Show move cursor when middle mouse button is pressed */
.pdf-pin-draggable:active {
  cursor: move;
}

.pdf-pin-icon:hover {
  color: #2563eb;
  transform: scale(1.3);
  z-index: 22;
}

.pdf-pin-icon :deep(.el-button) {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4), 0 2px 4px rgba(0, 0, 0, 0.1);
}

.pdf-pin-icon:hover :deep(.el-button) {
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.5), 0 4px 8px rgba(0, 0, 0, 0.15);
}

.pdf-pin-temporary {
  opacity: 0.8;
  animation: pinAppear 0.2s ease-out;
}

/* Temporary pins can have a slightly different appearance */
.pdf-pin-temporary {
  opacity: 0.7;
}

.pdf-pin-temporary :deep(.el-button) {
  opacity: 0.9;
}

@keyframes pinAppear {
  from {
    opacity: 0;
    transform: scale(0.5);
  }
  to {
    opacity: 0.8;
    transform: scale(1);
  }
}

.pdf-pin-icon svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
}

.loading-spinner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 2rem;
  color: #78716c;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
  z-index: 5;
}

.pdf-nav-buttons {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  transform: translateY(-50%);
  pointer-events: none;
  z-index: 1000;
}

.nav-button-floating {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgba(28, 25, 23, 0.8);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  pointer-events: auto !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 1001;
}

.nav-button-floating:hover {
  background: rgba(28, 25, 23, 1);
  transform: translateY(-50%) scale(1.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.nav-button-prev {
  left: 20px;
}

.nav-button-next {
  right: 20px;
}
</style>
