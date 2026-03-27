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
  const rgba = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/)
  if (rgba && rgba[4] !== undefined) return Math.round(parseFloat(rgba[4]) * 100)
  return 100
}

/** Extract base hex from rgba or return as-is for hex */
export function colorToHex(color: string): string {
  const rgba = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (rgba) {
    const r = parseInt(rgba[1], 10).toString(16).padStart(2, '0')
    const g = parseInt(rgba[2], 10).toString(16).padStart(2, '0')
    const b = parseInt(rgba[3], 10).toString(16).padStart(2, '0')
    return `#${r}${g}${b}`
  }
  return color
}
