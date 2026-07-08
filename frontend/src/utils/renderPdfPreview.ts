import { gunzipSync } from 'fflate'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'

import { stampWatermarkOnElement } from '@/utils/caseSquareWatermark'

let workerConfigured = false

function ensurePdfWorker(): void {
  if (workerConfigured) return
  const base = import.meta.env.BASE_URL.replace(/\/?$/, '/')
  GlobalWorkerOptions.workerSrc = `${base}pdf.worker.min.mjs`
  workerConfigured = true
}

export type RenderPdfPreviewOptions = {
  url: string
  container: HTMLElement
  scale?: number
  signal?: AbortSignal
  watermarkText?: string
}

function withCacheBust(url: string): string {
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}mg_preview=${Date.now()}`
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

async function fetchPdfBytes(url: string, signal?: AbortSignal): Promise<Uint8Array> {
  const response = await fetch(withCacheBust(url), {
    credentials: 'include',
    cache: 'no-store',
    signal,
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch PDF (${response.status})`)
  }
  return normalizePdfBytes(new Uint8Array(await response.arrayBuffer()))
}

async function renderPdfCanvas(
  data: Uint8Array,
  container: HTMLElement,
  scale: number,
  signal?: AbortSignal,
  watermarkText?: string
): Promise<void> {
  ensurePdfWorker()
  const loadingTask = getDocument({ data, isEvalSupported: false, disableAutoFetch: true })
  if (signal) {
    signal.addEventListener('abort', () => loadingTask.destroy(), { once: true })
  }
  const pdf = await loadingTask.promise
  if (signal?.aborted) {
    pdf.destroy()
    return
  }

  container.replaceChildren()
  for (let pageNum = 1; pageNum <= pdf.numPages; pageNum += 1) {
    if (signal?.aborted) break
    const page = await pdf.getPage(pageNum)
    const viewport = page.getViewport({ scale })
    const canvas = document.createElement('canvas')
    canvas.className = 'case-square-pdf-page mx-auto block max-w-full shadow-sm'
    const context = canvas.getContext('2d')
    if (!context) continue
    canvas.width = viewport.width
    canvas.height = viewport.height
    await page.render({ canvasContext: context, viewport }).promise

    const pageWrap = document.createElement('div')
    pageWrap.className = 'case-square-pdf-page-wrap case-square-watermark-host relative mx-auto mb-4 max-w-full'
    pageWrap.appendChild(canvas)
    if (watermarkText?.trim()) {
      stampWatermarkOnElement(pageWrap, watermarkText.trim())
    }
    container.appendChild(pageWrap)
  }
  pdf.destroy()
}

function renderPdfBlobIframe(data: Uint8Array, container: HTMLElement): () => void {
  container.replaceChildren()
  const blob = new Blob([data.slice()], { type: 'application/pdf' })
  const objectUrl = URL.createObjectURL(blob)
  const iframe = document.createElement('iframe')
  iframe.className = 'case-square-pdf-frame block w-full min-h-[70vh] border-0 bg-white'
  iframe.title = 'PDF preview'
  iframe.src = `${objectUrl}#toolbar=0&navpanes=0&view=FitH`
  container.appendChild(iframe)
  return () => URL.revokeObjectURL(objectUrl)
}

export async function renderPdfPreview(options: RenderPdfPreviewOptions): Promise<() => void> {
  const { url, container, scale = 1.35, signal, watermarkText } = options
  const data = await fetchPdfBytes(url, signal)

  try {
    await renderPdfCanvas(data, container, scale, signal, watermarkText)
    return () => {}
  } catch {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    return renderPdfBlobIframe(data, container)
  }
}
