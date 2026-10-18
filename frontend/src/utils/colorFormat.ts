const HEX6 = /^#([0-9a-f]{6})$/i
const HEX8 = /^#([0-9a-f]{8})$/i
const HEX3 = /^#([0-9a-f]{3})$/i
const RGB_CHANNELS =
  /^rgba?\(\s*([\d.]+)(?:\s*,\s*|\s+)([\d.]+)(?:\s*,\s*|\s+)([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/i

function channelToHex(value: string): string {
  const n = Math.max(0, Math.min(255, Math.round(Number.parseFloat(value))))
  return n.toString(16).padStart(2, '0')
}

function expandShortHex(short: string): string {
  return `#${short[0]}${short[0]}${short[1]}${short[1]}${short[2]}${short[2]}`.toLowerCase()
}

/** Convert hex to rgba with opacity (0-100) */
export function hexToRgba(hex: string, opacityPercent: number): string {
  const alpha = Math.max(0, Math.min(100, opacityPercent)) / 100
  const match = hex.replace('#', '').match(/.{2}/g)
  if (!match || match.length < 3) return hex
  const [r, g, b] = match.map((x) => parseInt(x, 16))
  return `rgba(${r},${g},${b},${alpha})`
}

/** Parse alpha from rgba() or return 100 for hex */
export function parseAlphaFromColor(color: string): number {
  const rgba = RGB_CHANNELS.exec(color.trim())
  if (rgba?.[4] === undefined) return 100
  const raw = rgba[4]
  if (raw.endsWith('%')) return Math.round(Number.parseFloat(raw))
  return Math.round(Number.parseFloat(raw) * 100)
}

/** Extract base hex from rgb/rgba, or return hex/other values as-is */
export function colorToHex(color: string): string {
  const trimmed = color.trim()
  const rgb = RGB_CHANNELS.exec(trimmed)
  if (rgb) {
    return `#${channelToHex(rgb[1])}${channelToHex(rgb[2])}${channelToHex(rgb[3])}`
  }
  const short = HEX3.exec(trimmed)
  if (short) return expandShortHex(short[1])
  return color
}

/** `#rrggbb` for `<input type="color">`. Non-hex and transparent become `fallback`. */
export function nativeColorInputHex(color: string | undefined, fallback = '#ffffff'): string {
  if (!color) return fallback
  const trimmed = color.trim()
  if (!trimmed || trimmed.toLowerCase() === 'transparent') return fallback
  const hex = colorToHex(trimmed)
  const six = HEX6.exec(hex)
  if (six) return `#${six[1].toLowerCase()}`
  const eight = HEX8.exec(hex)
  if (eight) return `#${eight[1].slice(0, 6).toLowerCase()}`
  return fallback
}

/** True when two CSS colors resolve to the same opaque hex (or both transparent). */
export function hexColorsEqual(left: string | undefined, right: string | undefined): boolean {
  if (!left || !right) return false
  const a = left.trim().toLowerCase()
  const b = right.trim().toLowerCase()
  if (a === b) return true
  if (a === 'transparent' || b === 'transparent') return false
  const leftHex = nativeColorInputHex(left, '')
  const rightHex = nativeColorInputHex(right, '')
  return Boolean(leftHex) && leftHex === rightHex
}
