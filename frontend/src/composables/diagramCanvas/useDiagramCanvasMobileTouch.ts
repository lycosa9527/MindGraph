import type { Ref } from 'vue'
import { ref } from 'vue'

import type { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'
import { ZOOM } from '@/config/uiConfig'

type BranchMove = ReturnType<typeof useBranchMoveDrag>

export function useDiagramCanvasMobileTouch(options: {
  canvasContainer: Ref<HTMLElement | null>
  getViewport: () => { x: number; y: number; zoom: number }
  setViewport: (
    viewport: { x: number; y: number; zoom: number },
    opts?: { duration?: number }
  ) => void
  branchMove: BranchMove
}): {
  setupMobileTouchZoom: () => void
  mobileTouchCleanup: Ref<(() => void) | null>
} {
  const { canvasContainer, getViewport, setViewport, branchMove } = options
  const mobileTouchCleanup = ref<(() => void) | null>(null)

  function setupMobileTouchZoom(): void {
    if (!canvasContainer.value) return
    const el = canvasContainer.value as HTMLElement

    let pinchStartDist = 0
    let pinchStartZoom = 1
    let pinchStartCenterX = 0
    let pinchStartCenterY = 0
    let pinchStartVpX = 0
    let pinchStartVpY = 0
    let isPinching = false

    let isPanning = false
    let panStartX = 0
    let panStartY = 0
    let panStartVpX = 0
    let panStartVpY = 0
    let panStartZoom = 1

    function isOnNode(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false
      return !!target.closest('.vue-flow__node')
    }

    function onTouchStart(e: TouchEvent): void {
      if (e.touches.length >= 2) {
        isPanning = false
        isPinching = true
        const t0 = e.touches[0]
        const t1 = e.touches[1]
        pinchStartDist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY)
        pinchStartCenterX = (t0.clientX + t1.clientX) / 2
        pinchStartCenterY = (t0.clientY + t1.clientY) / 2
        const vp = getViewport()
        pinchStartZoom = vp.zoom
        pinchStartVpX = vp.x
        pinchStartVpY = vp.y
        e.stopPropagation()
        return
      }

      if (e.touches.length === 1 && !isOnNode(e.target)) {
        if (branchMove.state.value.active) {
          branchMove.cancelDrag()
          return
        }
        isPanning = true
        const vp = getViewport()
        panStartX = e.touches[0].clientX
        panStartY = e.touches[0].clientY
        panStartVpX = vp.x
        panStartVpY = vp.y
        panStartZoom = vp.zoom
        e.stopPropagation()
      }
    }

    function onTouchMove(e: TouchEvent): void {
      if (isPinching && e.touches.length >= 2 && pinchStartDist > 0) {
        e.preventDefault()
        e.stopPropagation()

        const t0 = e.touches[0]
        const t1 = e.touches[1]
        const curDist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY)
        const curCenterX = (t0.clientX + t1.clientX) / 2
        const curCenterY = (t0.clientY + t1.clientY) / 2

        const scale = curDist / pinchStartDist
        const newZoom = Math.max(ZOOM.MIN, Math.min(ZOOM.MAX, pinchStartZoom * scale))

        const rect = el.getBoundingClientRect()
        const anchorX = pinchStartCenterX - rect.left
        const anchorY = pinchStartCenterY - rect.top
        const flowX = (anchorX - pinchStartVpX) / pinchStartZoom
        const flowY = (anchorY - pinchStartVpY) / pinchStartZoom

        const panDx = curCenterX - pinchStartCenterX
        const panDy = curCenterY - pinchStartCenterY

        const newX = anchorX - flowX * newZoom + panDx
        const newY = anchorY - flowY * newZoom + panDy

        setViewport({ x: newX, y: newY, zoom: newZoom }, { duration: 0 })
        return
      }

      if (isPanning && e.touches.length === 1) {
        e.preventDefault()
        e.stopPropagation()

        const dx = e.touches[0].clientX - panStartX
        const dy = e.touches[0].clientY - panStartY
        setViewport(
          { x: panStartVpX + dx, y: panStartVpY + dy, zoom: panStartZoom },
          { duration: 0 }
        )
      }
    }

    function onTouchEnd(e: TouchEvent): void {
      if (e.touches.length < 2) {
        isPinching = false
        pinchStartDist = 0
      }
      if (e.touches.length === 0) {
        isPanning = false
      }
    }

    el.addEventListener('touchstart', onTouchStart, { capture: true, passive: true })
    el.addEventListener('touchmove', onTouchMove, { capture: true, passive: false })
    el.addEventListener('touchend', onTouchEnd, { capture: true, passive: true })

    mobileTouchCleanup.value = () => {
      el.removeEventListener('touchstart', onTouchStart, { capture: true })
      el.removeEventListener('touchmove', onTouchMove, { capture: true })
      el.removeEventListener('touchend', onTouchEnd, { capture: true })
    }
  }

  return {
    setupMobileTouchZoom,
    mobileTouchCleanup,
  }
}
