/**
 * Canvas input mode is bound to this browser's device cookie, not the account.
 * The cookie is httpOnly and sent only to /api/auth.
 */
import { parseCanvasInputMode } from '@/config/canvasInputMode'
import type { CanvasInputMode } from '@/config/canvasInputMode'

const CANVAS_INPUT_DEVICE_PATH = '/api/auth/canvas-input-device'

export type CanvasInputDeviceFetch = CanvasInputMode | 'missing' | 'unavailable'

export async function fetchCanvasInputDevice(): Promise<CanvasInputDeviceFetch> {
  try {
    const response = await fetch(CANVAS_INPUT_DEVICE_PATH, { credentials: 'same-origin' })
    if (response.status === 404) return 'missing'
    if (!response.ok) return 'unavailable'
    const data = (await response.json()) as { input_mode?: unknown }
    const mode = parseCanvasInputMode(typeof data.input_mode === 'string' ? data.input_mode : null)
    return mode ?? 'unavailable'
  } catch {
    return 'unavailable'
  }
}

export async function saveCanvasInputDevice(mode: CanvasInputMode): Promise<boolean> {
  try {
    const response = await fetch(CANVAS_INPUT_DEVICE_PATH, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ input_mode: mode }),
    })
    return response.ok
  } catch {
    return false
  }
}
