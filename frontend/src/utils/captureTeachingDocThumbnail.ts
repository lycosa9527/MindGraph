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
const PDF_THUMB_SCALE = 1.25
const DOCX_CAPTURE_HOST_STYLE =
  'position:fixed;left:0;top:0;z-index:-1;width:820px;max-height:1200px;overflow:hidden;' +
  'background:#fff;opacity:0;pointer-events:none;'

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

async function waitForDocxPreviewPaint(host: HTMLElement): Promise<HTMLElement | null> {
  const deadline = Date.now() + 10_000
  while (Date.now() < deadline) {
    await waitForNextPaint()
    const firstPage =
      (host.querySelector('.showcase-docx-wrapper section') as HTMLElement | null) ??
      (host.querySelector('.showcase-docx-wrapper article') as HTMLElement | null) ??
      (host.querySelector('.showcase-docx-wrapper') as HTMLElement | null)
    if (firstPage && firstPage.scrollHeight > 48 && firstPage.textContent?.trim()) {
      await new Promise((resolve) => setTimeout(resolve, 250))
      return firstPage
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

    const htmlToImage = await import('html-to-image')
    const dataUrl = await htmlToImage.toPng(captureTarget, {
      pixelRatio: 1.5,
      backgroundColor: '#ffffff',
      cacheBust: true,
    })
    const blob = await dataUrlToPngBlob(dataUrl)
    return acceptThumbnailBlob(blob)
  } finally {
    host.remove()
  }
}

/** Render the first page of a teaching-design document (PDF/DOCX) as a PNG thumbnail. */
export async function captureTeachingDocThumbnail(file: File): Promise<Blob | null> {
  const lower = file.name.toLowerCase()
  if (lower.endsWith('.pdf')) return capturePdfFirstPage(file)
  if (lower.endsWith('.docx')) return captureDocxFirstPage(file)
  return null
}

export function isLegacyTeachingDocFile(name: string): boolean {
  const lower = name.toLowerCase()
  return lower.endsWith('.doc') && !lower.endsWith('.docx')
}
