import { gunzipSync } from 'fflate'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'

import {
  acceptThumbnailBlob,
  dataUrlToPngBlob,
  isValidThumbnailBlob,
} from '@/components/showcase/showcaseShared'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'
import { renderDocxPreview } from '@/utils/renderDocxPreview'

const THUMB_MAX_WIDTH = 960
const PDF_THUMB_SCALE = 1.1
const SVG_NS = 'http://www.w3.org/2000/svg'
const XLINK_NS = 'http://www.w3.org/1999/xlink'
/** Off-screen (not opacity:0) so html-to-image can rasterize painted pixels. */
const DOCX_CAPTURE_HOST_STYLE =
  'position:fixed;left:-10000px;top:0;width:720px;max-height:960px;overflow:hidden;' +
  'background:#fff;pointer-events:none;'

let workerConfigured = false

function ensurePdfWorker(): void {
  if (workerConfigured) return
  const base = import.meta.env.BASE_URL.replace(/\/?$/, '/')
  GlobalWorkerOptions.workerSrc = `${base}pdf.worker.min.mjs`
  workerConfigured = true
}

function normalizePdfBytes(data: Uint8Array): Uint8Array {
  if (data.byteLength >= 5) {
    const head = String.fromCharCode(...data.subarray(0, 5))
    if (head === '%PDF-') return data
  }
  if (data.byteLength >= 2 && data[0] === 0x1f && data[1] === 0x8b) {
    return gunzipSync(data)
  }
  throw new Error('Invalid PDF payload')
}

async function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  let target = canvas
  if (canvas.width > THUMB_MAX_WIDTH) {
    const scale = THUMB_MAX_WIDTH / canvas.width
    const scaled = document.createElement('canvas')
    scaled.width = Math.round(canvas.width * scale)
    scaled.height = Math.round(canvas.height * scale)
    const ctx = scaled.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(canvas, 0, 0, scaled.width, scaled.height)
    target = scaled
  }
  return new Promise((resolve) => {
    target.toBlob((blob) => resolve(isValidThumbnailBlob(blob) ? blob : null), 'image/png', 0.92)
  })
}

function readSvgImageHref(el: Element): string {
  // Avoid `instanceof SVGImageElement` — jsdom test env may not define it.
  const animated = (el as Element & { href?: { baseVal?: string } }).href
  if (animated && typeof animated === 'object') {
    const base = String(animated.baseVal ?? '').trim()
    if (base) return base
  }
  return (
    el.getAttribute('href')?.trim() ||
    el.getAttributeNS(XLINK_NS, 'href')?.trim() ||
    el.getAttribute('xlink:href')?.trim() ||
    ''
  )
}

/**
 * docx-preview draws Word shapes as SVG ``<image>`` nodes with empty href and
 * nested ``foreignObject`` text. html-to-image treats ``<image>`` as bitmaps and
 * rejects empty/broken hrefs (``Failed to parse URL from ?…``), aborting cover capture.
 */
export function sanitizeDocxDomForHtmlCapture(root: HTMLElement): void {
  root.querySelectorAll('image').forEach((el) => {
    const href = readSvgImageHref(el)
    if (href && !href.startsWith('?')) return
    if (el.childNodes.length > 0) {
      const group = document.createElementNS(SVG_NS, 'g')
      while (el.firstChild) {
        group.appendChild(el.firstChild)
      }
      el.replaceWith(group)
      return
    }
    el.remove()
  })

  root.querySelectorAll('img').forEach((img) => {
    const src = img.getAttribute('src')?.trim() || ''
    if (!src || src.startsWith('?')) {
      img.remove()
    }
  })
}

function pageHasCaptureContent(el: HTMLElement): boolean {
  if (el.scrollHeight <= 48) return false
  if (el.textContent?.trim()) return true
  return Boolean(el.querySelector('img, svg, table, canvas'))
}

function pickDocxCaptureTarget(host: HTMLElement): HTMLElement | null {
  const pages = [
    ...host.querySelectorAll<HTMLElement>('.showcase-docx-wrapper section'),
    ...host.querySelectorAll<HTMLElement>('.showcase-docx-wrapper article'),
  ]
  const contentful = pages.find((el) => pageHasCaptureContent(el))
  if (contentful) return contentful
  const wrapper = host.querySelector<HTMLElement>('.showcase-docx-wrapper')
  if (wrapper && pageHasCaptureContent(wrapper)) return wrapper
  return null
}

async function waitForDocxPreviewPaint(host: HTMLElement): Promise<HTMLElement | null> {
  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    await waitForNextPaint()
    const target = pickDocxCaptureTarget(host)
    if (target) {
      await new Promise((resolve) => setTimeout(resolve, 250))
      return target
    }
    await new Promise((resolve) => setTimeout(resolve, 120))
  }
  return null
}

async function capturePdfFirstPage(file: File): Promise<Blob | null> {
  ensurePdfWorker()
  const data = normalizePdfBytes(new Uint8Array(await file.arrayBuffer()))
  const loadingTask = getDocument({ data, isEvalSupported: false, disableAutoFetch: true })
  const pdf = await loadingTask.promise
  try {
    const page = await pdf.getPage(1)
    const viewport = page.getViewport({ scale: PDF_THUMB_SCALE })
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    if (!context) return null
    canvas.width = viewport.width
    canvas.height = viewport.height
    await page.render({ canvasContext: context, viewport }).promise
    return acceptThumbnailBlob(await canvasToPngBlob(canvas))
  } finally {
    pdf.destroy()
  }
}

async function captureDocxFirstPage(file: File): Promise<Blob | null> {
  const host = document.createElement('div')
  host.style.cssText = DOCX_CAPTURE_HOST_STYLE
  document.body.appendChild(host)
  try {
    await renderDocxPreview(file, host)
    const captureTarget = await waitForDocxPreviewPaint(host)
    if (!captureTarget) return null

    sanitizeDocxDomForHtmlCapture(host)

    const htmlToImage = await import('html-to-image')
    // Keep pixelRatio at 1 — docx first-page PNGs easily exceed the 2MB cover limit.
    // cacheBust:false avoids fetch storms on leftover empty SVG hrefs.
    const dataUrl = await htmlToImage.toPng(captureTarget, {
      pixelRatio: 1,
      backgroundColor: '#ffffff',
      cacheBust: false,
      width: Math.min(captureTarget.scrollWidth || THUMB_MAX_WIDTH, THUMB_MAX_WIDTH),
      height: Math.min(captureTarget.scrollHeight || 960, 960),
    })
    const blob = await dataUrlToPngBlob(dataUrl)
    return acceptThumbnailBlob(blob)
  } finally {
    host.remove()
  }
}

/** Render the first page of a teaching-design document (PDF/DOCX) as a PNG thumbnail. */
export async function captureTeachingDocThumbnail(file: File): Promise<Blob | null> {
  try {
    const lower = file.name.toLowerCase()
    if (lower.endsWith('.pdf')) return await capturePdfFirstPage(file)
    if (lower.endsWith('.docx')) return await captureDocxFirstPage(file)
    return null
  } catch (error) {
    console.warn('[Showcase] teaching doc cover capture failed', error)
    return null
  }
}

export function isLegacyTeachingDocFile(name: string): boolean {
  const lower = name.toLowerCase()
  return lower.endsWith('.doc') && !lower.endsWith('.docx')
}
