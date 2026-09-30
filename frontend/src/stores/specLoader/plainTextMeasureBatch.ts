/**
 * Measure many plain-text labels in one layout.
 * Numbering fills these maps, then the existing width/height functions read them.
 */
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

/** Text styles copied from the shared single-node measurer. Position stays on the host. */
const MEASURE_TEXT_CSS = [
  'white-space:pre-wrap',
  'word-break:normal',
  'overflow-wrap:break-word',
  'line-break:auto',
  'text-align:center',
  'line-height:1.4',
  'box-sizing:border-box',
].join(';')

export type NowrapMeasureSpec = {
  key: string
  text: string
  fontSize: number
  fontWeight: string
  fontFamily: string
}

export type BoxMeasureSpec = {
  key: string
  text: string
  fontSize: number
  fontWeight: string
  fontFamily: string
  maxWidth: number | undefined
  paddingX: number
  paddingY: number
}

export type TextBox = { width: number; height: number }

let nowrapLookup: Map<string, number> | null = null
let boxLookup: Map<string, TextBox> | null = null
let measureHost: HTMLDivElement | null = null

export function plainTextNowrapKey(
  text: string,
  fontSize: number,
  fontWeight: string,
  fontFamily: string
): string {
  return `n\u0001${fontSize}\u0001${fontWeight}\u0001${fontFamily}\u0001${text}`
}

export function plainTextBoxKey(
  text: string,
  fontSize: number,
  fontWeight: string,
  fontFamily: string,
  maxWidth: number | undefined,
  paddingX: number,
  paddingY: number
): string {
  const cap = maxWidth == null ? '' : String(maxWidth)
  return `b\u0001${fontSize}\u0001${fontWeight}\u0001${fontFamily}\u0001${paddingX}\u0001${paddingY}\u0001${cap}\u0001${text}`
}

export function cachedPlainTextWidth(key: string): number | undefined {
  return nowrapLookup?.get(key)
}

export function cachedPlainTextBox(key: string): TextBox | undefined {
  return boxLookup?.get(key)
}

export function withPlainTextMeasureLookup<T>(
  nowrap: Map<string, number>,
  boxes: Map<string, TextBox>,
  run: () => T
): T {
  const previousNowrap = nowrapLookup
  const previousBoxes = boxLookup
  nowrapLookup = nowrap
  boxLookup = boxes
  try {
    return run()
  } finally {
    nowrapLookup = previousNowrap
    boxLookup = previousBoxes
  }
}

function hostElement(): HTMLDivElement | null {
  if (typeof document === 'undefined') return null
  if (measureHost && document.body.contains(measureHost)) return measureHost
  measureHost = document.createElement('div')
  measureHost.setAttribute('aria-hidden', 'true')
  measureHost.style.cssText = [
    'position:absolute',
    'left:-9999px',
    'top:0',
    'width:max-content',
    'visibility:hidden',
    'pointer-events:none',
  ].join(';')
  document.body.appendChild(measureHost)
  return measureHost
}

function readHostSizes(host: HTMLDivElement, count: number): TextBox[] {
  const sizes: TextBox[] = []
  try {
    for (let index = 0; index < count; index += 1) {
      const el = host.children.item(index) as HTMLElement | null
      sizes.push({ width: el?.offsetWidth ?? 0, height: el?.offsetHeight ?? 0 })
    }
    return sizes
  } finally {
    host.replaceChildren()
  }
}

export function measureNowrapBatch(specs: readonly NowrapMeasureSpec[]): Map<string, number> {
  const widths = new Map<string, number>()
  const host = hostElement()
  if (!host || specs.length === 0) return widths
  host.replaceChildren()
  for (const spec of specs) {
    const el = document.createElement('div')
    el.style.cssText = MEASURE_TEXT_CSS
    el.style.fontFamily = spec.fontFamily || DIAGRAM_NODE_FONT_STACK
    el.style.width = 'max-content'
    el.style.whiteSpace = 'nowrap'
    el.style.padding = '0'
    el.style.maxWidth = 'none'
    el.style.fontSize = `${spec.fontSize}px`
    el.style.fontWeight = spec.fontWeight
    el.textContent = spec.text
    host.appendChild(el)
  }
  const sizes = readHostSizes(host, specs.length)
  specs.forEach((spec, index) => {
    const width = sizes[index]?.width ?? 0
    if (width > 0) widths.set(spec.key, width)
  })
  return widths
}

export function measureBoxBatch(specs: readonly BoxMeasureSpec[]): Map<string, TextBox> {
  const boxes = new Map<string, TextBox>()
  const host = hostElement()
  if (!host || specs.length === 0) return boxes
  host.replaceChildren()
  for (const spec of specs) {
    const el = document.createElement('div')
    el.style.cssText = MEASURE_TEXT_CSS
    el.style.fontFamily = spec.fontFamily || DIAGRAM_NODE_FONT_STACK
    el.style.fontSize = `${spec.fontSize}px`
    el.style.fontWeight = spec.fontWeight
    el.style.padding = `${spec.paddingY}px ${spec.paddingX}px`
    el.style.lineHeight = '1.4'
    if (spec.maxWidth != null) {
      el.style.maxWidth = `${spec.maxWidth}px`
      el.style.width = 'max-content'
      el.style.whiteSpace = 'pre-wrap'
      el.style.wordBreak = 'normal'
    } else {
      el.style.width = 'max-content'
      el.style.whiteSpace = 'nowrap'
      el.style.maxWidth = 'none'
    }
    el.textContent = spec.text
    host.appendChild(el)
  }
  const sizes = readHostSizes(host, specs.length)
  specs.forEach((spec, index) => {
    const size = sizes[index]
    if (size && size.width > 0 && size.height > 0) boxes.set(spec.key, size)
  })
  return boxes
}
