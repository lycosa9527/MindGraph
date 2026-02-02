<script setup lang="ts">
/**
 * ImageViewer - Image-based document viewer with pin-based comments
 * Displays PDF pages as pre-rendered images
 * Users click on page to place pins, click pins to see comments
 */
import { computed, createApp, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElBadge, ElButton, ElIcon } from 'element-plus'
import ElementPlus from 'element-plus'

import { ChatRound } from '@element-plus/icons-vue'

import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

import { useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { useLibraryStore } from '@/stores/library'
import { getLibraryDocumentPageImageUrl } from '@/utils/apiClient'
import type { LibraryDanmaku } from '@/utils/apiClient'

interface Props {
  documentId: number
  totalPages: number
  danmaku?: LibraryDanmaku[] // Danmaku for current page to show pins
  initialPage?: number // Initial page to load (defaults to 1)
}

interface Emits {
  (e: 'pageChange', pageNumber: number): void
  (e: 'pinPlace', x: number, y: number, pageNumber: number): void
  (e: 'pinClick', danmakuId: number): void
  (e: 'zoomChange', zoom: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const authStore = useAuthStore()
const libraryStore = useLibraryStore()
const notify = useNotifications()

const containerRef = ref<HTMLElement | null>(null)
const imageRef = ref<HTMLImageElement | null>(null)
const pinsLayerRef = ref<HTMLElement | null>(null)
const currentPage = ref(1)
const zoom = ref(1.0)
const rotation = ref(0)
const loading = ref(false)
const pinMode = ref(false) // Pin placement mode - must be enabled from toolbar
const temporaryPin = ref<{ x: number; y: number } | null>(null) // Temporary pin shown immediately on click

const renderPinsTimeoutId = ref<number | null>(null)
const isUnmounted = ref(false)
const isRendering = ref(false)

// Pre-loading state
const preloadedPages = ref<Set<number>>(new Set())

// Navigation state
const canGoPrevious = computed(() => currentPage.value > 1)
const canGoNext = computed(() => currentPage.value < props.totalPages)

// Drag state
const draggingPin = ref<{
  danmakuId: number
  element: HTMLElement
  startX: number
  startY: number
  initialX: number
  initialY: number
} | null>(null)

// Toggle pin mode
function togglePinMode() {
  pinMode.value = !pinMode.value
  updateCursor()
  // Clear temporary pin when disabling pin mode
  if (!pinMode.value) {
    temporaryPin.value = null
    // Only render pins if refs are available
    if (pinsLayerRef.value && imageRef.value) {
      renderPins()
    }
  }
}

// Clear temporary pin (called from parent when comment panel closes)
function clearTemporaryPin() {
  temporaryPin.value = null
  // Only render pins if refs are available
  if (pinsLayerRef.value && imageRef.value) {
    renderPins()
  }
}

// Update cursor based on pin mode - use custom pin cursor
function updateCursor() {
  if (!containerRef.value) return

  if (pinMode.value) {
    // Use custom pin cursor
    containerRef.value.style.cursor =
      "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24'%3E%3Cpath d='M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z' fill='%233b82f6' stroke='white' stroke-width='1.5'/%3E%3Ccircle cx='12' cy='10' r='3' fill='white'/%3E%3C/svg%3E\") 12 24, crosshair"
    if (imageRef.value) {
      imageRef.value.style.cursor =
        "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24'%3E%3Cpath d='M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z' fill='%233b82f6' stroke='white' stroke-width='1.5'/%3E%3Ccircle cx='12' cy='10' r='3' fill='white'/%3E%3C/svg%3E\") 12 24, crosshair"
    }
  } else {
    containerRef.value.style.cursor = 'default'
    if (imageRef.value) {
      imageRef.value.style.cursor = 'default'
    }
  }
}

// Handle canvas click for pin placement
function handleImageClick(e: MouseEvent) {
  if (!pinMode.value || !imageRef.value) return

  const rect = imageRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top

  // Normalize coordinates to image intrinsic size
  const img = imageRef.value
  const scaleX = img.naturalWidth / rect.width
  const scaleY = img.naturalHeight / rect.height
  const normalizedX = Math.round(x * scaleX)
  const normalizedY = Math.round(y * scaleY)

  // Show temporary pin immediately
  temporaryPin.value = { x: normalizedX, y: normalizedY }

  // Emit pin placement event
  emit('pinPlace', normalizedX, normalizedY, currentPage.value)

  // Render pins to show temporary pin
  nextTick(() => {
    renderPins()
  })
}

// Handle pin click via event delegation
function handlePinClickDelegation(e: MouseEvent) {
  const target = e.target as HTMLElement
  const pinElement = target.closest('.pdf-pin-icon') as HTMLElement | null

  if (!pinElement) return

  const danmakuId = pinElement.dataset.danmakuId
  if (danmakuId) {
    e.stopPropagation()
    e.preventDefault()
    emit('pinClick', parseInt(danmakuId, 10))
  }
}

// Handle pin drag start (middle mouse button)
function handlePinDragStart(
  e: MouseEvent,
  danmakuId: number,
  pinElement: HTMLElement,
  danmaku: LibraryDanmaku
) {
  if (!canDragPin(danmaku) || !pinsLayerRef.value || !imageRef.value) return

  e.preventDefault()
  e.stopPropagation()

  // Get the pin's current CSS position (relative to pins layer)
  // This is what we set in renderPins: left and top in pixels
  const currentLeft = parseFloat(pinElement.style.left) || 0
  const currentTop = parseFloat(pinElement.style.top) || 0

  // Get mouse position relative to pins layer
  const pinsLayerRect = pinsLayerRef.value.getBoundingClientRect()
  const startX = e.clientX - pinsLayerRect.left
  const startY = e.clientY - pinsLayerRect.top

  draggingPin.value = {
    danmakuId,
    element: pinElement,
    startX,
    startY,
    initialX: currentLeft,
    initialY: currentTop,
  }

  pinElement.style.transition = 'none'

  // Add global mouse move and up handlers
  document.addEventListener('mousemove', handlePinDrag)
  document.addEventListener('mouseup', handlePinDragEnd)
}

// Handle pin drag
function handlePinDrag(e: MouseEvent) {
  if (!draggingPin.value || !imageRef.value || !pinsLayerRef.value) return

  // Calculate mouse position relative to pins layer
  const pinsLayerRect = pinsLayerRef.value.getBoundingClientRect()
  const currentX = e.clientX - pinsLayerRect.left
  const currentY = e.clientY - pinsLayerRect.top

  // Calculate delta from start position
  const deltaX = currentX - draggingPin.value.startX
  const deltaY = currentY - draggingPin.value.startY

  // Calculate new position relative to pins layer
  const pinElement = draggingPin.value.element
  const newX = draggingPin.value.initialX + deltaX
  const newY = draggingPin.value.initialY + deltaY

  pinElement.style.left = `${newX}px`
  pinElement.style.top = `${newY}px`
}

// Handle pin drag end
function handlePinDragEnd(_e: MouseEvent) {
  if (!draggingPin.value || !imageRef.value || !pinsLayerRef.value) return

  const pinElement = draggingPin.value.element

  // Get the pin's current CSS position (relative to pins layer)
  // Note: pin has transform: translate(-50%, -50%), so left/top represent the CENTER of the pin
  const pinCenterX = parseFloat(pinElement.style.left) || 0
  const pinCenterY = parseFloat(pinElement.style.top) || 0

  // Get image and pins layer bounding rects
  const imageRect = imageRef.value.getBoundingClientRect()
  const pinsLayerRect = pinsLayerRef.value.getBoundingClientRect()

  // Calculate offset between pins layer top-left and image top-left
  // The pins layer covers the wrapper (100% width/height), but image might be smaller and centered
  const offsetX = imageRect.left - pinsLayerRect.left
  const offsetY = imageRect.top - pinsLayerRect.top

  // Calculate pin center position relative to image's top-left corner
  // pinCenterX/pinCenterY are relative to pins layer, so subtract the offset to get position relative to image
  const pinCenterXRelativeToImage = pinCenterX - offsetX
  const pinCenterYRelativeToImage = pinCenterY - offsetY

  // Get image natural and displayed dimensions
  const img = imageRef.value
  const displayedWidth = imageRect.width
  const displayedHeight = imageRect.height

  // Calculate scale factors (displayed size / natural size)
  const scaleX = displayedWidth / img.naturalWidth
  const scaleY = displayedHeight / img.naturalHeight

  // Convert from displayed image coordinates to normalized (natural image) coordinates
  // This is the inverse of what we do in renderPins: displayX = x * scaleX, so x = displayX / scaleX
  const normalizedX = Math.round(pinCenterXRelativeToImage / scaleX)
  const normalizedY = Math.round(pinCenterYRelativeToImage / scaleY)

  // Ensure coordinates are within bounds
  const clampedX = Math.max(0, Math.min(normalizedX, img.naturalWidth))
  const clampedY = Math.max(0, Math.min(normalizedY, img.naturalHeight))

  // Update danmaku position via API
  libraryStore
    .updateDanmakuPosition(draggingPin.value.danmakuId, {
      position_x: clampedX,
      position_y: clampedY,
    })
    .then(() => {
      // Re-render pins to update positions
      renderPins()
    })
    .catch((error) => {
      console.error('[ImageViewer] Failed to update pin position:', error)
      notify.error('Failed to update pin position')
      // Revert pin position
      renderPins()
    })

  pinElement.style.transition = ''
  draggingPin.value = null

  document.removeEventListener('mousemove', handlePinDrag)
  document.removeEventListener('mouseup', handlePinDragEnd)
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
  danmaku?: LibraryDanmaku
): HTMLDivElement {
  const pinDiv = document.createElement('div')
  pinDiv.className = isTemporary ? 'pdf-pin-icon pdf-pin-temporary' : 'pdf-pin-icon'
  pinDiv.style.pointerEvents = 'auto'
  if (danmakuId) {
    pinDiv.dataset.danmakuId = danmakuId.toString()
  }

  // Check if this pin can be dragged (for visual indication)
  const draggable = !isTemporary && danmaku && canDragPin(danmaku)
  if (draggable) {
    pinDiv.classList.add('pdf-pin-draggable')
  }

  // Calculate total comments (main comment + replies)
  const totalComments = repliesCount + 1

  // Create a Vue component: Badge wrapping Button with Icon
  const iconComponent = h(
    ElBadge,
    {
      value: !isTemporary && totalComments > 0 ? totalComments : 0,
      max: 99,
      hidden: isTemporary || totalComments === 0,
    },
    {
      default: () =>
        h(
          ElButton,
          {
            type: 'primary',
            circle: true,
            size: 'default',
            style: {
              width: '36px',
              height: '36px',
              padding: '0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            },
          },
          {
            default: () =>
              h(
                ElIcon,
                {
                  size: 20,
                },
                {
                  default: () => h(ChatRound),
                }
              ),
          }
        ),
    }
  )

  // Mount the Vue component to the div
  try {
    const app = createApp({
      render: () => iconComponent,
    })
    app.use(ElementPlus)
    app.mount(pinDiv)

    mountedPinApps.set(pinDiv, app)

    nextTick(() => {
      pinDiv.style.pointerEvents = 'auto'
    })
  } catch (error) {
    console.error('[ImageViewer] Failed to mount pin icon:', error)
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
    pinDiv.style.pointerEvents = 'auto'
  }

  // Track if we're dragging to prevent click events
  let isDragging = false

  // Add click handler directly to pin element
  if (danmakuId) {
    pinDiv.addEventListener(
      'click',
      (e) => {
        // Don't trigger click if we just finished dragging or if currently dragging
        if (draggingPin.value || isDragging) {
          isDragging = false
          return
        }

        // Don't trigger click for middle mouse button
        if (e.button === 1) {
          return
        }

        e.stopPropagation()
        e.preventDefault()

        emit('pinClick', danmakuId)
      },
      true
    )
  }

  // Add drag event listeners for all pins (middle mouse button only)
  if (danmakuId) {
    pinDiv.addEventListener('mousedown', (e) => {
      if (e.button === 1) {
        e.preventDefault()
        e.stopPropagation()
        isDragging = false

        const pinDanmaku = danmaku || (props.danmaku || []).find((d) => d.id === danmakuId)
        if (pinDanmaku) {
          handlePinDragStart(e, danmakuId, pinDiv, pinDanmaku)
          isDragging = true
        }
      }
    })

    // Mark drag as ended when mouse is released
    pinDiv.addEventListener('mouseup', (e) => {
      if (e.button === 1 && isDragging) {
        // Small delay to prevent click event from firing
        setTimeout(() => {
          isDragging = false
        }, 100)
      }
    })
  }

  return pinDiv
}

// Render pin icons for danmaku on current page
function renderPins() {
  if (!pinsLayerRef.value || !imageRef.value) {
    return
  }

  const pinsLayer = pinsLayerRef.value
  const image = imageRef.value

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

  // Get image dimensions (intrinsic size)
  const imageIntrinsicWidth = image.naturalWidth
  const imageIntrinsicHeight = image.naturalHeight

  if (imageIntrinsicWidth === 0 || imageIntrinsicHeight === 0) {
    return
  }

  // Get displayed image dimensions and pins layer rect for offset calculation
  const imageRect = image.getBoundingClientRect()
  const pinsLayerRect = pinsLayer.getBoundingClientRect()
  const displayedWidth = imageRect.width
  const displayedHeight = imageRect.height

  // Calculate scale factors
  const scaleX = displayedWidth / imageIntrinsicWidth
  const scaleY = displayedHeight / imageIntrinsicHeight

  // Calculate offset between pins layer and image
  // The pins layer covers the wrapper (100% width/height), but image might be smaller and centered
  const offsetX = imageRect.left - pinsLayerRect.left
  const offsetY = imageRect.top - pinsLayerRect.top

  // Get current page danmaku
  const currentPageDanmaku = (props.danmaku || []).filter(
    (d) => d.page_number === currentPage.value
  )

  // Render pins for danmaku
  for (const danmaku of currentPageDanmaku) {
    const x = danmaku.position_x || 0
    const y = danmaku.position_y || 0

    // Calculate displayed position (normalized -> displayed)
    // x and y are normalized coordinates (relative to natural image size)
    const displayX = x * scaleX
    const displayY = y * scaleY

    // Create pin element
    const repliesCount = danmaku.replies_count || 0
    const pinElement = createPinIconElement(danmaku.id, false, repliesCount, danmaku)

    // Position pin relative to pins layer
    // displayX/displayY are relative to displayed image, so add offset to get position relative to pins layer
    pinElement.style.position = 'absolute'
    pinElement.style.left = `${displayX + offsetX}px`
    pinElement.style.top = `${displayY + offsetY}px`
    pinElement.style.transform = 'translate(-50%, -50%)'
    pinElement.style.zIndex = '10'

    pinsLayer.appendChild(pinElement)
  }

  // Render temporary pin if in pin mode
  if (pinMode.value && temporaryPin.value) {
    const tempPinElement = createPinIconElement(null, true, 0)
    const tempDisplayX = temporaryPin.value.x * scaleX
    const tempDisplayY = temporaryPin.value.y * scaleY
    tempPinElement.style.position = 'absolute'
    tempPinElement.style.left = `${tempDisplayX + offsetX}px`
    tempPinElement.style.top = `${tempDisplayY + offsetY}px`
    tempPinElement.style.transform = 'translate(-50%, -50%)'
    tempPinElement.style.zIndex = '10'
    tempPinElement.style.opacity = '0.7'

    pinsLayer.appendChild(tempPinElement)
  }
}

// Pre-load pages into browser cache
function preloadPages(pageNumbers: number[]) {
  if (isUnmounted.value) return

  pageNumbers.forEach((pageNum) => {
    if (pageNum < 1 || pageNum > props.totalPages) return
    if (preloadedPages.value.has(pageNum)) return // Already pre-loaded

    const imageUrl = getLibraryDocumentPageImageUrl(props.documentId, pageNum)
    const img = new Image()
    img.src = imageUrl
    preloadedPages.value.add(pageNum)
  })
}

// Load and render current page image
async function renderPage(pageNum: number) {
  if (pageNum < 1 || pageNum > props.totalPages) return

  if (isUnmounted.value) {
    return
  }

  // Prevent duplicate renders
  if (isRendering.value && currentPage.value === pageNum) {
    return
  }

  isRendering.value = true
  loading.value = true
  try {
    await nextTick()

    if (!imageRef.value) {
      isRendering.value = false
      loading.value = false
      return
    }

    // Load image (may already be cached from pre-loading)
    const imageUrl = getLibraryDocumentPageImageUrl(props.documentId, pageNum)
    imageRef.value.src = imageUrl

    // Wait for image to load
    await new Promise<void>((resolve, reject) => {
      if (!imageRef.value) {
        reject(new Error('Image ref not available'))
        return
      }

      if (imageRef.value.complete) {
        resolve()
        return
      }

      imageRef.value.onload = () => resolve()
      imageRef.value.onerror = () => {
        reject(new Error('Failed to load image'))
      }
    })

    // Check again after image loads
    if (isUnmounted.value) {
      return
    }

    // Update current page
    if (currentPage.value !== pageNum) {
      currentPage.value = pageNum
      emit('pageChange', pageNum)
    }

    // Set default zoom to 100% (1.0) after image loads
    await nextTick()
    if (imageRef.value && containerRef.value && !isUnmounted.value) {
      // Wait a bit for image natural dimensions to be available
      if (imageRef.value.naturalWidth > 0 && imageRef.value.naturalHeight > 0) {
        // Default view is 100% zoom
        zoom.value = 1.0
        emit('zoomChange', zoom.value)
      } else {
        // If dimensions not ready, wait for image load event
        imageRef.value.addEventListener(
          'load',
          () => {
            if (!isUnmounted.value && imageRef.value && containerRef.value) {
              zoom.value = 1.0
              emit('zoomChange', zoom.value)
            }
          },
          { once: true }
        )
      }
    }

    // Render pins after image is loaded
    await nextTick()
    if (renderPinsTimeoutId.value !== null) {
      clearTimeout(renderPinsTimeoutId.value)
      renderPinsTimeoutId.value = null
    }
    renderPinsTimeoutId.value = window.setTimeout(() => {
      renderPinsTimeoutId.value = null
      if (isUnmounted.value) {
        return
      }
      if (pinsLayerRef.value && imageRef.value) {
        renderPins()
      }
    }, 50)

    // Update cursor
    updateCursor()
  } catch (error) {
    if (!isUnmounted.value) {
      // Check if this is a 404 error (page doesn't exist)
      // Log and notify user
      console.error(`[ImageViewer] Failed to render page ${pageNum}:`, error)
      notify.error(`Failed to load page ${pageNum}`)
    }
  } finally {
    if (!isUnmounted.value) {
      loading.value = false
      isRendering.value = false
    }
  }
}

// Navigation functions
async function goToPage(pageNum: number) {
  if (pageNum < 1 || pageNum > props.totalPages) {
    return
  }
  renderPage(pageNum)
}

async function goToPreviousPage() {
  if (currentPage.value <= 1) {
    return
  }
  await goToPage(currentPage.value - 1)
}

async function goToNextPage() {
  if (currentPage.value >= props.totalPages) {
    return
  }
  await goToPage(currentPage.value + 1)
}

// Zoom functions
function adjustZoom(delta: number) {
  zoom.value = Math.max(0.5, Math.min(3.0, zoom.value + delta))
  emit('zoomChange', zoom.value)
  // Re-render pins after zoom
  nextTick(() => {
    renderPins()
  })
}

function setZoom(value: number) {
  zoom.value = Math.max(0.5, Math.min(3.0, value))
  emit('zoomChange', zoom.value)
  // Re-render pins after zoom
  nextTick(() => {
    renderPins()
  })
}

function fitToWidth() {
  if (!containerRef.value || !imageRef.value) return

  // Wait for image dimensions
  if (imageRef.value.naturalWidth === 0 || imageRef.value.naturalHeight === 0) {
    requestAnimationFrame(() => {
      if (!isUnmounted.value && containerRef.value && imageRef.value) {
        fitToWidth()
      }
    })
    return
  }

  // Get the actual visible canvas width from the container
  // The container is the full viewport area
  const containerWidth = containerRef.value.clientWidth
  const imageWidth = imageRef.value.naturalWidth

  if (imageWidth === 0) return

  // Account for navigation buttons and padding
  // Navigation buttons are 56px each side, positioned at left: 20px and right: 20px
  // We want the image to not overlap with buttons, so reserve space
  const buttonWidth = 56
  const buttonMargin = 20
  const reservedSpace = (buttonWidth + buttonMargin) * 2 // Both sides
  const padding = 40 // Additional padding for breathing room
  const availableWidth = Math.max(200, containerWidth - reservedSpace - padding)

  // Calculate zoom to fill the available canvas width
  const newZoom = availableWidth / imageWidth

  // Clamp zoom between reasonable bounds (allow smaller zoom for very wide images)
  zoom.value = Math.max(0.15, Math.min(3.0, newZoom))
  emit('zoomChange', zoom.value)
  nextTick(() => {
    renderPins()
  })
}

function fitToPage() {
  if (!containerRef.value || !imageRef.value) return

  // Get actual container dimensions
  const containerWidth = containerRef.value.clientWidth
  const containerHeight = containerRef.value.clientHeight

  // Get image natural dimensions
  const imageWidth = imageRef.value.naturalWidth
  const imageHeight = imageRef.value.naturalHeight

  // Wait for image to have dimensions
  if (imageWidth === 0 || imageHeight === 0) {
    // If dimensions not ready, wait for next frame
    requestAnimationFrame(() => {
      if (!isUnmounted.value && containerRef.value && imageRef.value) {
        fitToPage()
      }
    })
    return
  }

  // Account for navigation buttons (56px each side) and padding
  // Reduced padding to allow larger initial view
  const horizontalPadding = 100 // Navigation buttons (56px * 2) + minimal padding
  const verticalPadding = 60 // Top/bottom padding

  // Calculate available space
  const availableWidth = Math.max(100, containerWidth - horizontalPadding)
  const availableHeight = Math.max(100, containerHeight - verticalPadding)

  // Calculate zoom ratios
  const zoomWidth = availableWidth / imageWidth
  const zoomHeight = availableHeight / imageHeight

  // Use the smaller ratio to fit both dimensions, but ensure minimum zoom of 0.3
  // This prevents images from being too small
  const newZoom = Math.max(0.3, Math.min(zoomWidth, zoomHeight))

  // Clamp zoom between reasonable bounds
  zoom.value = Math.max(0.3, Math.min(3.0, newZoom))
  emit('zoomChange', zoom.value)

  nextTick(() => {
    renderPins()
  })
}

// Rotate function
function rotate() {
  rotation.value = (rotation.value + 90) % 360
  // Re-render pins after rotation
  nextTick(() => {
    renderPins()
  })
}

// Download function (not applicable for images, but kept for interface compatibility)
function downloadImage() {
  if (!imageRef.value?.src) return
  const link = document.createElement('a')
  link.href = imageRef.value.src
  link.download = `document-${props.documentId}-page-${currentPage.value}.jpg`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Print function - triggers browser's print modal
function printImage() {
  if (!imageRef.value?.src) return

  // Create a new window with just the image for printing
  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    notify.error('无法打开打印窗口，请检查浏览器弹窗设置')
    return
  }

  const pageNum = currentPage.value
  const imageSrc = imageRef.value.src
  const scriptTag = '</' + 'script>'

  // Build HTML content with the image
  const htmlContent =
    '<!DOCTYPE html>\n' +
    '<html>\n' +
    '<head>\n' +
    '<title>打印 - 页面 ' +
    pageNum +
    '</title>\n' +
    '<style>\n' +
    'body { margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; }\n' +
    'img { max-width: 100%; max-height: 100vh; object-fit: contain; }\n' +
    '@media print { body { padding: 0; } img { width: 100%; height: auto; } }\n' +
    '</style>\n' +
    '</head>\n' +
    '<body>\n' +
    '<img src="' +
    imageSrc +
    '" alt="页面 ' +
    pageNum +
    '" />\n' +
    '<script>\n' +
    'window.onload = function() {\n' +
    '  window.print();\n' +
    '  window.onafterprint = function() { window.close(); };\n' +
    '};\n' +
    scriptTag +
    '\n' +
    '</body>\n' +
    '</html>'

  printWindow.document.write(htmlContent)
  printWindow.document.close()
}

// Handle window resize
let resizeTimeout: number | null = null
function handleResize() {
  if (resizeTimeout) {
    clearTimeout(resizeTimeout)
  }
  resizeTimeout = window.setTimeout(() => {
    if (currentPage.value && imageRef.value && containerRef.value) {
      // Re-fit image to canvas width on resize (adaptive to current width)
      fitToWidth()
      renderPins()
    }
  }, 250)
}

// Handle keyboard navigation
function handleKeyDown(e: KeyboardEvent) {
  // Don't handle if user is typing in an input field
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
    return
  }

  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    goToPreviousPage()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    goToNextPage()
  }
}

// Watch for danmaku changes
watch(
  () => props.danmaku,
  () => {
    if (pinsLayerRef.value && imageRef.value) {
      renderPins()
    }
  },
  { deep: true }
)

// Watch for image size changes and re-render pins
// This handles cases where the container resizes (e.g., when comment panel opens/closes)
let resizeObserver: ResizeObserver | null = null
watch(
  () => imageRef.value,
  (newImage) => {
    // Clean up previous observer
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }

    if (newImage && containerRef.value) {
      // Observe container for size changes (image size changes will trigger container resize)
      resizeObserver = new ResizeObserver(() => {
        if (pinsLayerRef.value && imageRef.value && !isUnmounted.value) {
          // Debounce re-rendering to avoid excessive updates
          if (renderPinsTimeoutId.value !== null) {
            clearTimeout(renderPinsTimeoutId.value)
          }
          renderPinsTimeoutId.value = window.setTimeout(() => {
            renderPinsTimeoutId.value = null
            if (!isUnmounted.value && pinsLayerRef.value && imageRef.value) {
              renderPins()
            }
          }, 150)
        }
      })

      resizeObserver.observe(containerRef.value)
    }
  },
  { immediate: true }
)

// Watch for page changes (only for preloading, not rendering)
watch(
  () => currentPage.value,
  (newPage, oldPage) => {
    // Skip if page hasn't actually changed
    if (newPage === oldPage) {
      return
    }

    // Pre-load next pages when user navigates
    // Pre-load current page + 1 and + 2 if not already loaded
    if (newPage > 0 && newPage <= props.totalPages) {
      const pagesToPreload: number[] = []
      if (newPage + 1 <= props.totalPages && !preloadedPages.value.has(newPage + 1)) {
        pagesToPreload.push(newPage + 1)
      }
      if (newPage + 2 <= props.totalPages && !preloadedPages.value.has(newPage + 2)) {
        pagesToPreload.push(newPage + 2)
      }
      if (pagesToPreload.length > 0) {
        preloadPages(pagesToPreload)
      }
    }
  }
)


// Watch for documentId or totalPages changes to pre-load initial pages
watch(
  [() => props.documentId, () => props.totalPages],
  ([docId, total]) => {
    if (docId && total && total > 0 && !isUnmounted.value) {
      const pagesToPreload = [1, 2, 3].filter((page) => page <= total)
      preloadPages(pagesToPreload)
    }
  },
  { immediate: false }
)

onMounted(async () => {
  isUnmounted.value = false

  await nextTick()

  let retries = 0
  const maxRetries = 20
  while ((!containerRef.value || !imageRef.value || !pinsLayerRef.value) && retries < maxRetries) {
    await new Promise((resolve) => setTimeout(resolve, 50))
    retries++
  }

  if (isUnmounted.value) {
    return
  }

  // Set up click handler for placing pins directly on image
  if (imageRef.value) {
    imageRef.value.addEventListener('click', handleImageClick)
  }

  // Set up pin click handler using event delegation on container
  if (containerRef.value) {
    containerRef.value.addEventListener('click', handlePinClickDelegation, true)
  }

  // Pre-load first 3 pages for faster navigation
  if (props.documentId && props.totalPages > 0) {
    const pagesToPreload = [1, 2, 3].filter((page) => page <= props.totalPages)
    preloadPages(pagesToPreload)
  }

  // Load initial page (from prop or default to 1)
  const initialPage = props.initialPage || 1
  if (imageRef.value && pinsLayerRef.value) {
    renderPage(initialPage)
  }

  // Initialize cursor
  updateCursor()

  // Ensure default zoom is 100% on initial load
  // The zoom is already set to 1.0 in renderPage, but we ensure it's maintained
  await nextTick()
  if (imageRef.value && containerRef.value && !isUnmounted.value) {
    // Ensure zoom is at 100% if it hasn't been set yet
    if (zoom.value === 1.0) {
      emit('zoomChange', zoom.value)
    }
  }

  window.addEventListener('resize', handleResize)
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  isUnmounted.value = true

  // Clear timeout
  if (renderPinsTimeoutId.value !== null) {
    clearTimeout(renderPinsTimeoutId.value)
    renderPinsTimeoutId.value = null
  }

  // Clean up pin Vue apps
  if (pinsLayerRef.value) {
    const existingPins = pinsLayerRef.value.querySelectorAll('.pdf-pin-icon')
    existingPins.forEach((pin) => {
      const app = mountedPinApps.get(pin as HTMLDivElement)
      if (app) {
        app.unmount()
        mountedPinApps.delete(pin as HTMLDivElement)
      }
    })
  }

  // Remove event listeners
  if (imageRef.value) {
    imageRef.value.removeEventListener('click', handleImageClick)
  }
  if (containerRef.value) {
    containerRef.value.removeEventListener('click', handlePinClickDelegation)
  }

  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeyDown)

  // Clean up drag handlers
  document.removeEventListener('mousemove', handlePinDrag)
  document.removeEventListener('mouseup', handlePinDragEnd)

  // Clean up resize observer
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
})

// Expose methods and state for parent component
defineExpose({
  currentPage,
  totalPages: () => props.totalPages,
  zoom,
  pinMode,
  goToPage: (page: number) => goToPage(page),
  goToPreviousPage: () => goToPreviousPage(),
  goToNextPage: () => goToNextPage(),
  zoomIn: () => adjustZoom(0.1),
  zoomOut: () => adjustZoom(-0.1),
  setZoom: (value: number) => setZoom(value),
  rotate: () => rotate(),
  download: () => downloadImage(),
  print: () => printImage(),
  togglePinMode: () => togglePinMode(),
  clearTemporaryPin: () => clearTemporaryPin(),
  renderPins: () => renderPins(),
  fitToPage: () => fitToPage(),
})
</script>

<template>
  <div
    ref="containerRef"
    v-loading="loading"
    element-loading-text="加载中..."
    element-loading-background="rgba(255, 255, 255, 0.8)"
    class="image-viewer-container"
  >
    <!-- Previous Page Button (Left) -->
    <button
      v-if="canGoPrevious"
      :disabled="loading"
      aria-label="Previous page"
      class="nav-button nav-button-left"
      @click="goToPreviousPage"
    >
      <ChevronLeft :size="32" />
    </button>

    <!-- Next Page Button (Right) -->
    <button
      v-if="canGoNext"
      :disabled="loading"
      aria-label="Next page"
      class="nav-button nav-button-right"
      @click="goToNextPage"
    >
      <ChevronRight :size="32" />
    </button>

    <div
      class="image-canvas-wrapper"
      :style="{ transform: `rotate(${rotation}deg)` }"
    >
      <img
        ref="imageRef"
        class="page-image"
        :style="{
          maxWidth: '100%',
          maxHeight: '100%',
          width: 'auto',
          height: 'auto',
          objectFit: 'contain',
          transform: `scale(${zoom})`,
          transformOrigin: 'center center',
        }"
        alt="Page image"
      />
      <div
        ref="pinsLayerRef"
        class="pins-layer"
      />
    </div>
  </div>
</template>

<style scoped>
.image-viewer-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  background-color: #f5f5f5;
}

.nav-button {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 50;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background-color: #000;
  border: 2px solid #000;
  box-shadow: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
  color: #fff;
  font-weight: 500;
}

.nav-button:hover:not(:disabled) {
  background-color: #333;
  border-color: #333;
  transform: translateY(-50%);
}

.nav-button:active:not(:disabled) {
  background-color: #000;
  transform: translateY(-50%);
}

.nav-button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  background-color: #666;
  border-color: #666;
}

.nav-button-left {
  left: 20px;
}

.nav-button-right {
  right: 20px;
}

.image-canvas-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
}

.page-image {
  display: block;
  user-select: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-width: 100%;
  max-height: 100%;
}

.pins-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
