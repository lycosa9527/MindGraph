/**
 * Mobile haptic feedback for the Kitty click wheel and similar touch UI.
 *
 * - Android: standard Vibration API (`navigator.vibrate`).
 * - iOS Safari 17.4+: hidden `<input type="checkbox" switch>` click, which
 *   triggers the Taptic Engine (Apple's only web haptics path today).
 * - Desktop / unsupported: silent no-op.
 *
 * Calls must stay synchronous inside a user gesture (touch/pointer handler).
 */

const SELECTION_PULSE_MS = 12
const ENGAGE_PULSE_MS = 8

let iosSwitchInput: HTMLInputElement | null = null

function hasVibrationApi(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function'
}

function isIosTouchDevice(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const ua = navigator.userAgent
  if (/iPad|iPhone|iPod/.test(ua)) {
    return true
  }
  return navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
}

function ensureIosSwitchInput(): HTMLInputElement | null {
  if (typeof document === 'undefined') {
    return null
  }
  if (iosSwitchInput && document.body.contains(iosSwitchInput)) {
    return iosSwitchInput
  }
  const input = document.createElement('input')
  input.type = 'checkbox'
  input.setAttribute('switch', '')
  input.style.position = 'fixed'
  input.style.opacity = '0'
  input.style.width = '1px'
  input.style.height = '1px'
  input.style.pointerEvents = 'none'
  input.style.left = '-9999px'
  input.tabIndex = -1
  input.setAttribute('aria-hidden', 'true')
  document.body.appendChild(input)
  iosSwitchInput = input
  return input
}

/** iOS 17.4+ Safari switch-input Taptic pulse. */
function pulseIosSwitch(): void {
  const input = ensureIosSwitchInput()
  if (!input) {
    return
  }
  try {
    input.checked = !input.checked
    input.click()
  } catch {
    // Platform restriction — ignore.
  }
}

function runHaptic(durationMs: number): void {
  if (hasVibrationApi()) {
    try {
      navigator.vibrate(durationMs)
      return
    } catch {
      // Fall through to iOS switch when vibrate throws.
    }
  }
  if (isIosTouchDevice()) {
    pulseIosSwitch()
  }
}

/** Short detent pulse when the click wheel lands on a node. */
export function pulseDeviceSelection(): void {
  runHaptic(SELECTION_PULSE_MS)
}

/** Lighter pulse when the user engages the wheel ring. */
export function pulseDeviceEngage(): void {
  runHaptic(ENGAGE_PULSE_MS)
}

/** Whether any haptic path is likely available on this device. */
export function isDeviceHapticSupported(): boolean {
  return hasVibrationApi() || isIosTouchDevice()
}
