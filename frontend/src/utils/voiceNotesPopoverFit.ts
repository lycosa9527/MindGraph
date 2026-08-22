/**
 * Keep Voice Notes popovers (说话人编辑 + merge menu) inside the visible frame.
 */

export type VoiceNotesRectBox = {
  left: number
  top: number
  right: number
  bottom: number
}

export type VoiceNotesPopoverPlacement = {
  top: number
  left: number
  maxHeight: number
  maxWidth: number
}

export const VOICE_NOTES_POPOVER_PAD = 8
export const VOICE_NOTES_POPOVER_GAP = 8
const MIN_POPOVER_HEIGHT = 96
const MIN_POPOVER_WIDTH = 120

export function visualViewportClip(padding = VOICE_NOTES_POPOVER_PAD): VoiceNotesRectBox {
  const view = typeof window !== 'undefined' ? window.visualViewport : null
  if (view) {
    return {
      left: view.offsetLeft + padding,
      top: view.offsetTop + padding,
      right: view.offsetLeft + view.width - padding,
      bottom: view.offsetTop + view.height - padding,
    }
  }
  const width = typeof window !== 'undefined' ? window.innerWidth : 1024
  const height = typeof window !== 'undefined' ? window.innerHeight : 768
  return {
    left: padding,
    top: padding,
    right: width - padding,
    bottom: height - padding,
  }
}

export function placePopoverNearTrigger(
  trigger: VoiceNotesRectBox,
  size: { width: number; height: number },
  preferred: 'above' | 'below',
  clip: VoiceNotesRectBox,
  gap = VOICE_NOTES_POPOVER_GAP
): VoiceNotesPopoverPlacement {
  const availBelow = clip.bottom - trigger.bottom - gap
  const availAbove = trigger.top - clip.top - gap
  const need = Math.min(size.height, MIN_POPOVER_HEIGHT)
  const openBelow =
    preferred === 'below'
      ? availBelow >= need || availBelow >= availAbove
      : availAbove < need && availBelow > availAbove

  const maxHeight = Math.max(MIN_POPOVER_HEIGHT, openBelow ? availBelow : availAbove)
  const height = Math.min(size.height, maxHeight)
  const rawTop = openBelow ? trigger.bottom + gap : trigger.top - gap - height
  const top = Math.min(Math.max(rawTop, clip.top), Math.max(clip.top, clip.bottom - height))

  const maxWidth = Math.max(MIN_POPOVER_WIDTH, clip.right - clip.left)
  const width = Math.min(size.width, maxWidth)
  let left = trigger.right - width
  if (left < clip.left) left = clip.left
  if (left + width > clip.right) left = clip.right - width
  if (left < clip.left) left = clip.left

  return { top, left, maxHeight, maxWidth }
}

export function popoverPlacementStyle(placed: VoiceNotesPopoverPlacement): Record<string, string> {
  return {
    position: 'fixed',
    top: `${Math.round(placed.top)}px`,
    left: `${Math.round(placed.left)}px`,
    maxHeight: `${Math.round(placed.maxHeight)}px`,
    maxWidth: `${Math.round(placed.maxWidth)}px`,
    zIndex: '4100',
  }
}
