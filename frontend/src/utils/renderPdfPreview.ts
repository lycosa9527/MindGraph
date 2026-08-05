import { gunzipSync } from 'fflate'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'

import { fetchShowcaseAsset } from '@/utils/fetchShowcaseAsset'
import { refreshWatermarkDensity, stampWatermarkOnElement } from '@/utils/showcaseWatermark'

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
  const response = await fetchShowcaseAsset(url, { signal })
  if (!response.ok) {
    throw new Error(`Failed to fetch PDF (${response.status})`)
  }
  return normalizePdfBytes(new Uint8Array(await response.arrayBuffer()))
}

function displayPixelRatio(): number {
  if (typeof window === 'undefined') return 1
  const ratio = window.devicePixelRatio || 1
  return Math.min(Math.max(ratio, 1), 2)
}

async function renderPdfCanvas(
  data: Uint8Array,
  container: HTMLElement,
  scale: number,
  signal?: AbortSignal,
  watermarkText?: string
): Promise<void> {
  ensurePdfWorker()
  // pdfjs 6: isEvalSupported removed; prefer canvas over canvasContext-only render.
  const loadingTask = getDocument({ data, disableAutoFetch: true })
  if (signal) {
    signal.addEventListener('abort', () => void loadingTask.destroy(), { once: true })
  }
  const pdf = await loadingTask.promise
  if (signal?.aborted) {
    await pdf.cleanup()
    return
  }

  const pixelRatio = displayPixelRatio()
  container.replaceChildren()
  for (let pageNum = 1; pageNum <= pdf.numPages; pageNum += 1) {
    if (signal?.aborted) break
    const page = await pdf.getPage(pageNum)
    const logicalViewport = page.getViewport({ scale })
    const renderViewport = page.getViewport({ scale: scale * pixelRatio })
    const canvas = document.createElement('canvas')
    canvas.className = 'showcase-pdf-page mx-auto block max-w-full'
    // Logical CSS width — never stretch with width:100% (keeps page aspect; avoids blur).
    canvas.style.width = `${logicalViewport.width}px`
    canvas.style.maxWidth = '100%'
    canvas.style.height = 'auto'
    const context = canvas.getContext('2d')
    if (!context) continue
    canvas.width = Math.floor(renderViewport.width)
    canvas.height = Math.floor(renderViewport.height)
    await page.render({ canvas, canvasContext: context, viewport: renderViewport }).promise

    const pageWrap = document.createElement('div')
    pageWrap.className =
      'showcase-pdf-page-wrap showcase-watermark-host relative mx-auto mb-4 max-w-full'
    pageWrap.style.width = 'fit-content'
    pageWrap.style.maxWidth = '100%'
    pageWrap.appendChild(canvas)
    if (watermarkText?.trim()) {
      stampWatermarkOnElement(pageWrap, watermarkText.trim())
    }
    container.appendChild(pageWrap)
  }
  await pdf.cleanup()
  if (watermarkText?.trim()) {
    refreshWatermarkDensity(container, watermarkText.trim())
  }
}

function renderPdfBlobIframe(data: Uint8Array, container: HTMLElement): () => void {
  container.replaceChildren()
  const blob = new Blob([data.slice()], { type: 'application/pdf' })
  const objectUrl = URL.createObjectURL(blob)
  const iframe = document.createElement('iframe')
  iframe.className = 'showcase-pdf-frame block w-full min-h-[70vh] border-0 bg-white'
  iframe.title = 'PDF preview'
  iframe.src = `${objectUrl}#toolbar=0&navpanes=0&view=FitH`
  container.appendChild(iframe)
  return () => URL.revokeObjectURL(objectUrl)
}

export async function renderPdfPreview(options: RenderPdfPreviewOptions): Promise<() => void> {
  const { url, container, scale = 1.5, signal, watermarkText } = options
  const data = await fetchPdfBytes(url, signal)

  try {
    await renderPdfCanvas(data, container, scale, signal, watermarkText)
    return () => {}
  } catch {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    return renderPdfBlobIframe(data, container)
  }
}
