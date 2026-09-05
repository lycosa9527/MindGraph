import {
  PRESENTATION_POINTER_SCALE_MAX,
  PRESENTATION_POINTER_SCALE_MIN,
} from '@/stores/presentationPointer'
import type { TrainingSpotlightShape, TrainingStepOverlay } from '@/types/training'

export function clampOverlayPercent(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(100, Math.max(0, value))
}

export function overlayClientPercent(
  box: Element,
  clientX: number,
  clientY: number
): { x: number; y: number } {
  const rect = box.getBoundingClientRect()
  const width = rect.width || 1
  const height = rect.height || 1
  return {
    x: clampOverlayPercent(((clientX - rect.left) / width) * 100),
    y: clampOverlayPercent(((clientY - rect.top) / height) * 100),
  }
}

export function translateOverlay(overlay: TrainingStepOverlay, dx: number, dy: number): void {
  overlay.x = clampOverlayPercent((overlay.x ?? 0) + dx)
  overlay.y = clampOverlayPercent((overlay.y ?? 0) + dy)
  if (overlay.kind !== 'arrow') return
  overlay.x2 = clampOverlayPercent((overlay.x2 ?? 0) + dx)
  overlay.y2 = clampOverlayPercent((overlay.y2 ?? 0) + dy)
}

export type ArrowHandle = 'start' | 'end'

export function moveArrowHandle(
  overlay: TrainingStepOverlay,
  handle: ArrowHandle,
  x: number,
  y: number
): void {
  if (handle === 'start') {
    overlay.x = clampOverlayPercent(x)
    overlay.y = clampOverlayPercent(y)
    return
  }
  overlay.x2 = clampOverlayPercent(x)
  overlay.y2 = clampOverlayPercent(y)
}

export function clampSpotlightScale(value: number): number {
  if (!Number.isFinite(value)) return 1
  const rounded = Math.round(value * 10) / 10
  return Math.min(PRESENTATION_POINTER_SCALE_MAX, Math.max(PRESENTATION_POINTER_SCALE_MIN, rounded))
}

export function spotlightRadius(overlay: TrainingStepOverlay): number {
  if (typeof overlay.r === 'number') return clampSpotlightScale(overlay.r)
  const legacy = ((overlay.w ?? 22) + (overlay.h ?? 16)) / 2
  return clampSpotlightScale(legacy / 22)
}

export function spotlightShape(
  overlay?: TrainingStepOverlay | null
): TrainingSpotlightShape {
  return overlay?.shape === 'rect' ? 'rect' : 'circle'
}
