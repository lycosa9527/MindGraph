/**
 * Bake Kitty PTT copy into an SVG image so iOS cannot select the label.
 */

export const KITTY_MIC_PTT_LABEL_FONT =
  'system-ui, "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", sans-serif'

export const KITTY_MIC_PTT_LABEL_COLOR = '#ffffff'
export const KITTY_MIC_PTT_LABEL_FONT_SIZE_PX = 13
export const KITTY_MIC_PTT_LABEL_FONT_WEIGHT = 600

export type KittyMicPttLabelMode = 'manual' | 'auto'

export function resolveKittyMicPttLabelText(
  listenMode: KittyMicPttLabelMode,
  voiceActive: boolean,
  pttActive: boolean,
  translate: (key: string, fallback: string) => string
): string {
  if (listenMode === 'auto') {
    return voiceActive
      ? translate('mobile.kittyTapToStopListen', '点按停止')
      : translate('mobile.kittyTapToListen', '点按开始听')
  }
  if (voiceActive || pttActive) {
    return translate('mobile.kittyReleaseToSend', '松开发送')
  }
  return translate('mobile.kittyHoldToSpeak', '按住说话')
}

export function escapeSvgText(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

export function estimateKittyMicPttLabelWidthPx(text: string, fontSizePx: number): number {
  let width = 0
  for (const ch of text) {
    const code = ch.codePointAt(0) ?? 0
    const isWide =
      (code >= 0x1100 && code <= 0x11ff) ||
      (code >= 0x2e80 && code <= 0x9fff) ||
      (code >= 0xac00 && code <= 0xd7af) ||
      (code >= 0xf900 && code <= 0xfaff) ||
      (code >= 0xff00 && code <= 0xffef)
    width += isWide ? fontSizePx : fontSizePx * 0.62
  }
  return Math.ceil(width)
}

export function kittyMicPttLabelImageSrc(text: string): string {
  const fontSizePx = KITTY_MIC_PTT_LABEL_FONT_SIZE_PX
  const paddingX = 1
  const paddingY = 2
  const textWidth = estimateKittyMicPttLabelWidthPx(text, fontSizePx)
  const width = Math.max(1, textWidth + paddingX * 2)
  const height = Math.max(1, Math.ceil(fontSizePx + paddingY * 2))
  const baseline = paddingY + fontSizePx * 0.8
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
    `viewBox="0 0 ${width} ${height}">` +
    `<text x="${width / 2}" y="${baseline}" fill="${KITTY_MIC_PTT_LABEL_COLOR}" ` +
    `font-size="${fontSizePx}" font-weight="${KITTY_MIC_PTT_LABEL_FONT_WEIGHT}" ` +
    `font-family="${escapeSvgText(KITTY_MIC_PTT_LABEL_FONT)}" text-anchor="middle">` +
    `${escapeSvgText(text)}` +
    `</text></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}
