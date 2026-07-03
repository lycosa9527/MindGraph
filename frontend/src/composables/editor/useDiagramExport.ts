/**
 * useDiagramExport - Composable for exporting MindGraph diagrams
 * Supports PNG, SVG, PDF (via html-to-image + jspdf), and MG interchange
 */
import { nextTick, ref } from 'vue'

import { applyThinkingCoinMutation, extractThinkingCoinsFooter } from '@/composables/auth/useThinkingCoinSync'
import { useNotifications } from '@/composables'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'
import { apiRequestJson } from '@/utils/apiClient'
import { getDiagramCanvasHtmlToImageOptions, waitForNextPaint } from '@/utils/diagramHtmlToImage'
import {
  addRasterImageToA4PdfPage,
  isPdfExportCommand,
  resolvePdfOrientationFromCommand,
  type PdfPageOrientation,
} from '@/utils/diagramPdfExport'
import { waitForDiagramExportFonts } from '@/utils/diagramExportPrep'
import { encodeMgFileContents } from '@/utils/mgInterchange'

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\?%*:|"<>]/g, '-').trim() || 'diagram'
}

function triggerDownload(dataUrl: string, filename: string): void {
  const link = document.createElement('a')
  link.download = filename
  link.href = dataUrl
  link.click()
}

function triggerDownloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.download = filename
  link.href = url
  link.click()
  URL.revokeObjectURL(url)
}

function logDiagramExport(format: string): void {
  apiRequestJson<Record<string, unknown>>('/api/activity/diagram_export', {
    method: 'POST',
    body: JSON.stringify({ format }),
  })
    .then((body) => {
      applyThinkingCoinMutation(extractThinkingCoinsFooter(body))
    })
    .catch(() => {
      /* Fire-and-forget; do not fail export if log fails */
    })
}

export interface UseDiagramExportOptions {
  getContainer: () => HTMLElement | null
  getDiagramSpec: () => Record<string, unknown> | null
  getTitle: () => string
}

async function loadImageFromDataUrl(dataUrl: string): Promise<HTMLImageElement> {
  const img = new Image()
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = reject
    img.src = dataUrl
  })
  return img
}

export function useDiagramExport(options: UseDiagramExportOptions) {
  const { getContainer, getDiagramSpec, getTitle } = options
  const { t } = useLanguage()
  const notify = useNotifications()
  const uiStore = useUIStore()
  const diagramStore = useDiagramStore()

  const isExporting = ref(false)

  async function waitForExportFonts(): Promise<void> {
    await waitForDiagramExportFonts(uiStore.promptLanguage)
  }

  async function loadHtmlToImage(): Promise<typeof import('html-to-image')> {
    return import('html-to-image')
  }

  async function captureContainerPng(
    container: HTMLElement
  ): Promise<{ dataUrl: string; width: number; height: number }> {
    const { toPng } = await loadHtmlToImage()
    const dataUrl = await toPng(container, getDiagramCanvasHtmlToImageOptions({ pixelRatio: 2 }))
    const img = await loadImageFromDataUrl(dataUrl)
    return { dataUrl, width: img.width, height: img.height }
  }

  async function waitForCanvasPaint(): Promise<void> {
    await nextTick()
    await waitForNextPaint()
  }

  async function buildA4PdfFromImages(
    images: Array<{ dataUrl: string; width: number; height: number }>,
    orientation: PdfPageOrientation
  ): Promise<InstanceType<(typeof import('jspdf'))['jsPDF']>> {
    const { jsPDF } = await import('jspdf')
    const pdf = new jsPDF({
      orientation,
      unit: 'mm',
      format: 'a4',
    })
    images.forEach((image, index) => {
      if (index > 0) {
        pdf.addPage('a4', orientation)
      }
      addRasterImageToA4PdfPage(pdf, image.dataUrl, image.width, image.height)
    })
    return pdf
  }

  async function exportAsPng(): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()
      const { toBlob } = await loadHtmlToImage()
      const blob = await toBlob(container, getDiagramCanvasHtmlToImageOptions())
      if (!blob) {
        throw new Error('PNG export produced empty image')
      }

      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownloadBlob(blob, `${baseName}_${timestamp}.png`)

      logDiagramExport('png')
      notify.success(t('canvas.export.pngSuccess'))
    } catch (error) {
      console.error('PNG export failed:', error)
      notify.error(t('canvas.export.pngError'))
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsSvg(): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()
      const { toSvg } = await loadHtmlToImage()
      const dataUrl = await toSvg(container, getDiagramCanvasHtmlToImageOptions())

      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownload(dataUrl, `${baseName}_${timestamp}.svg`)

      logDiagramExport('svg')
      notify.success(t('canvas.export.svgSuccess'))
    } catch (error) {
      console.error('SVG export failed:', error)
      notify.error(t('canvas.export.svgError'))
    } finally {
      isExporting.value = false
    }
  }

  async function exportLearningSheetPdf(
    container: HTMLElement,
    orientation: PdfPageOrientation,
    format: string
  ): Promise<void> {
    const savedShowAnswers = diagramStore.learningSheetShowAnswers
    diagramStore.setLearningSheetShowAnswers(false)
    await waitForCanvasPaint()

    const worksheetCapture = await captureContainerPng(container)

    const answerCapture = await diagramStore.runWithLearningSheetAnswersRevealed(async () => {
      await waitForCanvasPaint()
      return captureContainerPng(container)
    })

    diagramStore.setLearningSheetShowAnswers(savedShowAnswers)

    const pdf = await buildA4PdfFromImages([worksheetCapture, answerCapture], orientation)
    const baseName = sanitizeFilename(getTitle())
    const timestamp = new Date().toISOString().slice(0, 10)
    pdf.save(`${baseName}_${timestamp}.pdf`)

    logDiagramExport(format)
    notify.success(t('canvas.export.pdfSuccess'))
  }

  async function exportAsPdf(format: string): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()

      const isLearningSheetExport =
        diagramStore.isLearningSheet && diagramStore.hasBlankedLearningSheetNodes()

      if (isLearningSheetExport) {
        const rect = container.getBoundingClientRect()
        const orientation = resolvePdfOrientationFromCommand(
          format,
          Math.round(rect.width),
          Math.round(rect.height)
        )
        await exportLearningSheetPdf(container, orientation, format)
        return
      }

      const probe = await captureContainerPng(container)
      const orientation = resolvePdfOrientationFromCommand(format, probe.width, probe.height)

      const pdf = await buildA4PdfFromImages([probe], orientation)
      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      pdf.save(`${baseName}_${timestamp}.pdf`)
      logDiagramExport(format)
      notify.success(t('canvas.export.pdfSuccess'))
    } catch (error) {
      console.error('PDF export failed:', error)
      notify.error(t('canvas.export.pdfError'))
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsMgFile(): Promise<void> {
    const spec = getDiagramSpec()
    if (!spec) {
      notify.warning(t('canvas.export.noDiagramData'))
      return
    }

    isExporting.value = true
    try {
      const json = JSON.stringify(spec)
      const bytes = await encodeMgFileContents(json)
      const blob = new Blob([new Uint8Array(bytes)], { type: 'application/octet-stream' })
      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownloadBlob(blob, `${baseName}_${timestamp}.mg`)

      logDiagramExport('mg')
      notify.success(t('canvas.export.jsonSuccess'))
    } catch (error) {
      console.error('MG export failed:', error)
      notify.error(t('canvas.export.jsonError'))
    } finally {
      isExporting.value = false
    }
  }

  async function exportByFormat(format: string): Promise<void> {
    switch (format) {
      case 'png':
        await exportAsPng()
        break
      case 'svg':
        await exportAsSvg()
        break
      case 'pdf':
      case 'pdf_landscape':
      case 'pdf_portrait':
        await exportAsPdf(format)
        break
      case 'mg':
        await exportAsMgFile()
        break
      default:
        if (isPdfExportCommand(format)) {
          await exportAsPdf(format)
          break
        }
        notify.warning(t('canvas.export.unknownFormat', { format }))
    }
  }

  return {
    exportAsPng,
    exportAsSvg,
    exportAsPdf,
    exportAsMgFile,
    exportByFormat,
    isExporting,
  }
}
