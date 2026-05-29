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
let iosSwitchLabel: HTMLLabelElement | null = null

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
  if (iosSwitchInput && iosSwitchLabel && document.body.contains(iosSwitchLabel)) {
    return iosSwitchInput
  }
  const label = document.createElement('label')
  label.style.position = 'fixed'
  label.style.opacity = '0'
  label.style.width = '1px'
  label.style.height = '1px'
  label.style.overflow = 'hidden'
  label.style.pointerEvents = 'none'
  label.style.left = '0'
  label.style.top = '0'
  label.tabIndex = -1
  label.setAttribute('aria-hidden', 'true')

  const input = document.createElement('input')
  input.type = 'checkbox'
  input.setAttribute('switch', '')
  input.tabIndex = -1
  input.setAttribute('aria-hidden', 'true')
  label.appendChild(input)
  document.body.appendChild(label)
  iosSwitchLabel = label
  iosSwitchInput = input
  return input
}

/** iOS 17.4+ Safari switch-input Taptic pulse (label click, not input.click). */
function pulseIosSwitch(): void {
  const input = ensureIosSwitchInput()
  if (!input || !iosSwitchLabel) {
    return
  }
  try {
    input.checked = false
    iosSwitchLabel.click()
  } catch {
    // Platform restriction — ignore.
  }
}

function runHaptic(durationMs: number): void {
  if (isIosTouchDevice()) {
    pulseIosSwitch()
    return
  }
  if (hasVibrationApi()) {
    try {
      navigator.vibrate(durationMs)
    } catch {
      // Unsupported — ignore.
    }
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
