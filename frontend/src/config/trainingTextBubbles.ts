import type { TrainingStepOverlay, TrainingTextAlign } from '@/types/training'

export const TRAINING_TEXT_WIDTH_DEFAULT = 28
export const TRAINING_TEXT_WIDTH_MIN = 12
export const TRAINING_TEXT_WIDTH_MAX = 72
export const TRAINING_TEXT_HEIGHT_DEFAULT = 16
export const TRAINING_TEXT_HEIGHT_MIN = 8
export const TRAINING_TEXT_HEIGHT_MAX = 56
export const TRAINING_TEXT_SIZE_DEFAULT = 18
export const TRAINING_TEXT_SIZE_MIN = 12
export const TRAINING_TEXT_SIZE_MAX = 40
export const TRAINING_TEXT_SIZE_STEP = 2
export const TRAINING_TEXT_INK_DEFAULT = '#1c1917'
export const TRAINING_TEXT_STROKE_DEFAULT = '#d6d3d1'
export const TRAINING_TEXT_DRAG_SLOP = 8

const HEX_COLOR = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

function clampRound(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) return fallback
  return Math.min(max, Math.max(min, Math.round(value * 10) / 10))
}

export function clampTextWidth(value: number): number {
  return clampRound(
    value,
    TRAINING_TEXT_WIDTH_MIN,
    TRAINING_TEXT_WIDTH_MAX,
    TRAINING_TEXT_WIDTH_DEFAULT
  )
}

export function clampTextHeight(value: number): number {
  return clampRound(
    value,
    TRAINING_TEXT_HEIGHT_MIN,
    TRAINING_TEXT_HEIGHT_MAX,
    TRAINING_TEXT_HEIGHT_DEFAULT
  )
}

export function clampTextSize(value: number): number {
  if (!Number.isFinite(value)) return TRAINING_TEXT_SIZE_DEFAULT
  const snapped = Math.round(value / TRAINING_TEXT_SIZE_STEP) * TRAINING_TEXT_SIZE_STEP
  return Math.min(TRAINING_TEXT_SIZE_MAX, Math.max(TRAINING_TEXT_SIZE_MIN, snapped))
}

export function textBubbleWidth(overlay: TrainingStepOverlay): number {
  return clampTextWidth(overlay.w ?? TRAINING_TEXT_WIDTH_DEFAULT)
}

export function textBubbleHeight(overlay: TrainingStepOverlay): number {
  return clampTextHeight(overlay.h ?? TRAINING_TEXT_HEIGHT_DEFAULT)
}

export function textBubbleFontSize(overlay: TrainingStepOverlay): number {
  return clampTextSize(overlay.size ?? TRAINING_TEXT_SIZE_DEFAULT)
}

export function textBubbleAlign(overlay: TrainingStepOverlay): TrainingTextAlign {
  if (overlay.align === 'center' || overlay.align === 'right') return overlay.align
  return 'left'
}

export function textBubbleIsBold(overlay: TrainingStepOverlay): boolean {
  return overlay.bold === true
}

export function textBubbleIsItalic(overlay: TrainingStepOverlay): boolean {
  return overlay.italic === true
}

export function resizeTextBubble(
  overlay: TrainingStepOverlay,
  pointerX: number,
  pointerY: number
): void {
  const left = (overlay.x ?? 50) - textBubbleWidth(overlay) / 2
  const top = (overlay.y ?? 42) - textBubbleHeight(overlay) / 2
  overlay.w = clampTextWidth(pointerX - left)
  overlay.h = clampTextHeight(pointerY - top)
}

export function bumpTextBubbleFont(overlay: TrainingStepOverlay, delta: number): void {
  overlay.size = clampTextSize(textBubbleFontSize(overlay) + delta)
}

export function toggleTextBubbleBold(overlay: TrainingStepOverlay): void {
  overlay.bold = !textBubbleIsBold(overlay)
}

export function toggleTextBubbleItalic(overlay: TrainingStepOverlay): void {
  overlay.italic = !textBubbleIsItalic(overlay)
}

export function setTextBubbleAlign(overlay: TrainingStepOverlay, align: TrainingTextAlign): void {
  overlay.align = align
}

export function normalizeTextHex(value: string | undefined, fallback: string): string {
  if (!value || !HEX_COLOR.test(value)) return fallback
  if (value.length === 4) {
    const red = value[1]
    const green = value[2]
    const blue = value[3]
    return `#${red}${red}${green}${green}${blue}${blue}`.toLowerCase()
  }
  return value.toLowerCase()
}

export function textBubbleInk(overlay: TrainingStepOverlay): string {
  return normalizeTextHex(overlay.ink, TRAINING_TEXT_INK_DEFAULT)
}

export function textBubbleStroke(overlay: TrainingStepOverlay): string {
  return normalizeTextHex(overlay.stroke, TRAINING_TEXT_STROKE_DEFAULT)
}

export function setTextBubbleInk(overlay: TrainingStepOverlay, value: string): void {
  overlay.ink = normalizeTextHex(value, TRAINING_TEXT_INK_DEFAULT)
}

export function setTextBubbleStroke(overlay: TrainingStepOverlay, value: string): void {
  overlay.stroke = normalizeTextHex(value, TRAINING_TEXT_STROKE_DEFAULT)
}

export function textBubbleDragReady(
  originX: number,
  originY: number,
  clientX: number,
  clientY: number
): boolean {
  const dx = clientX - originX
  const dy = clientY - originY
  return dx * dx + dy * dy >= TRAINING_TEXT_DRAG_SLOP * TRAINING_TEXT_DRAG_SLOP
}

export function textBubbleBox(overlay: TrainingStepOverlay): Record<string, string> {
  const stroke = textBubbleStroke(overlay)
  return {
    left: `${overlay.x ?? 50}%`,
    top: `${overlay.y ?? 42}%`,
    width: `${textBubbleWidth(overlay)}%`,
    height: `${textBubbleHeight(overlay)}%`,
    borderColor: stroke,
    '--bubble-stroke': stroke,
  }
}

export function textBubbleFaceStyle(overlay: TrainingStepOverlay): Record<string, string> {
  return {
    color: textBubbleInk(overlay),
    fontSize: `${textBubbleFontSize(overlay)}px`,
    fontWeight: textBubbleIsBold(overlay) ? '700' : '500',
    fontStyle: textBubbleIsItalic(overlay) ? 'italic' : 'normal',
    textAlign: textBubbleAlign(overlay),
  }
}
