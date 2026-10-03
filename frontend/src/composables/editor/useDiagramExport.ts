/**
 * useDiagramExport - Composable for exporting MindGraph diagrams
 * Mind maps: vector SVG + svg2pdf PDF + high-DPI SVG raster for DOCX.
 * Other types: PNG/SVG/PDF via html-to-image + jspdf; MG interchange.
 */
import { ref } from 'vue'

import type { jsPDF } from 'jspdf'

import { useNotifications } from '@/composables'
import {
  applyThinkingCoinMutation,
  extractThinkingCoinsFooter,
} from '@/composables/auth/useThinkingCoinSync'
import { useLanguage } from '@/composables/core/useLanguage'
import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import { hasActiveWorksheetHeader, resolveWorksheetTopicText } from '@/config/canvasWorksheetText'
import { specHasSecondaryText } from '@/diagramBilingual/mirror'
import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'
import { apiRequestJson, apiUpload } from '@/utils/apiClient'
import { copyPngBlobWithFallback } from '@/utils/copyPngBlobToClipboard'
import {
  type DeliverExportResult,
  dataUrlToBlob,
  deliverExportDataUrl,
  deliverExportFile,
} from '@/utils/deliverExportFile'
import { loadHtmlToImageModule } from '@/utils/diagramExportHtmlToImage'
import {
  isLearningSheetRasterCapture,
  runAsShownRasterCapture,
  runLearningSheetRasterCapture,
  waitForExportCanvasPaint,
} from '@/utils/diagramExportLearningSheet'
import { waitForDiagramExportFonts } from '@/utils/diagramExportPrep'
import {
  type DiagramRasterCapture,
  canvasToPngBlob,
  captureDiagramPngData,
  captureDiagramRasterCanvas,
} from '@/utils/diagramExportRasterCapture'
import {
  getDiagramCanvasHtmlToImageOptions,
  getDiagramCanvasPdfHtmlToImageOptions,
} from '@/utils/diagramHtmlToImage'
import {
  buildMindMapVectorSvgFromStores,
  canUseMindMapVectorExport,
  exportMindMapVectorDocxPng,
  exportMindMapVectorPdfDocument,
} from '@/utils/diagramMindMapVectorExport'
import type { MindMapVectorSvgResult } from '@/utils/diagramMindMapVectorSvg'
import {
  type PdfPageOrientation,
  addRasterImageToA4PdfPage,
  addWorksheetPageToPdf,
  compressRasterDataUrlForA4Pdf,
  isPdfExportCommand,
  resolvePdfOrientationFromExportOptions,
} from '@/utils/diagramPdfExport'
import { type WorksheetHeaderLabels, captureWorksheetHeader } from '@/utils/diagramWorksheetHeader'
import { applyLlmExportWatermarkToCanvas } from '@/utils/llmExportWatermark'
import { mergeCanvasExportOptions } from '@/utils/mergeCanvasExportOptions'
import { encodeMgFileContents } from '@/utils/mgInterchange'

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\?%*:|"<>]/g, '-').trim() || 'diagram'
}

function exportFilename(title: string, extension: string): string {
  const baseName = sanitizeFilename(title)
  const timestamp = new Date().toISOString().slice(0, 10)
  return `${baseName}_${timestamp}.${extension}`
}

async function handOffExportFile(blob: Blob, filename: string): Promise<boolean> {
  const result = await deliverExportFile(blob, filename)
  return result !== 'cancelled'
}

async function handOffPdf(pdf: jsPDF, filename: string): Promise<boolean> {
  return handOffExportFile(pdf.output('blob'), filename)
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

type PdfRasterCapture = DiagramRasterCapture

export function useDiagramExport(options: UseDiagramExportOptions) {
  const { getContainer, getDiagramSpec, getTitle } = options
  const { t } = useLanguage()
  const notify = useNotifications()
  const uiStore = useUIStore()
  const diagramStore = useDiagramStore()

  const isExporting = ref(false)

  function resolveExportOptions(exportOptions?: CanvasExportOptions): CanvasExportOptions {
    // Do not inject store worksheet into plain PDF — headers are opt-in on the payload.
    return mergeCanvasExportOptions(exportOptions)
  }

  async function waitForExportFonts(): Promise<void> {
    await waitForDiagramExportFonts(uiStore.promptLanguage)
  }

  async function captureContainerForPdfRaw(container: HTMLElement): Promise<PdfRasterCapture> {
    return captureDiagramPngData(container, getDiagramCanvasPdfHtmlToImageOptions())
  }

  async function captureContainerForPdf(
    container: HTMLElement,
    exportOptions?: CanvasExportOptions
  ): Promise<PdfRasterCapture> {
    return runLearningSheetRasterCapture(diagramStore, exportOptions, () =>
      captureContainerForPdfRaw(container)
    )
  }

  async function buildA4PdfFromImages(
    images: PdfRasterCapture[],
    orientation: PdfPageOrientation,
    headerCapture: PdfRasterCapture | null = null,
    exportOptions?: CanvasExportOptions
  ): Promise<InstanceType<(typeof import('jspdf'))['jsPDF']>> {
    const { jsPDF } = await import('jspdf')
    const pdf = new jsPDF({
      orientation,
      unit: 'mm',
      format: 'a4',
    })
    const worksheetText = resolveExportOptions(exportOptions).worksheetText
    const diagramOffsetX = worksheetText?.diagramOffsetX ?? 0
    const diagramOffsetY = worksheetText?.diagramOffsetY ?? 0
    const diagramScale = worksheetText?.diagramScale ?? 1
    const hasCustomPlacement = diagramOffsetX !== 0 || diagramOffsetY !== 0 || diagramScale !== 1
    for (let index = 0; index < images.length; index += 1) {
      const image = images[index]
      if (index > 0) {
        pdf.addPage('a4', orientation)
      }
      const compressed = await compressRasterDataUrlForA4Pdf(
        image.dataUrl,
        image.width,
        image.height,
        orientation,
        image.image
      )
      const includeHeader = headerCapture !== null && index === 0
      if (includeHeader && headerCapture) {
        addWorksheetPageToPdf(
          pdf,
          compressed.dataUrl,
          compressed.width,
          compressed.height,
          headerCapture.dataUrl,
          headerCapture.width,
          headerCapture.height,
          10,
          4,
          diagramOffsetX,
          diagramOffsetY,
          diagramScale
        )
      } else if (index === 0 && hasCustomPlacement && !headerCapture) {
        // No header, but user placed/resized the diagram — honor transform on page 1.
        addWorksheetPageToPdf(
          pdf,
          compressed.dataUrl,
          compressed.width,
          compressed.height,
          null,
          0,
          0,
          10,
          4,
          diagramOffsetX,
          diagramOffsetY,
          diagramScale
        )
      } else {
        addRasterImageToA4PdfPage(pdf, compressed.dataUrl, compressed.width, compressed.height)
      }
    }
    return pdf
  }

  function worksheetHeaderLabels(): WorksheetHeaderLabels {
    return {
      name: t('canvas.worksheetText.fieldName'),
      className: t('canvas.worksheetText.fieldClass'),
      date: t('canvas.worksheetText.fieldDate'),
      instructionPrefix: t('canvas.worksheetText.instructionPrefix'),
      defaultInstruction: t('canvas.worksheetText.defaultInstruction'),
    }
  }

  async function resolveWorksheetHeaderCapture(
    exportOptions?: CanvasExportOptions
  ): Promise<PdfRasterCapture | null> {
    const merged = resolveExportOptions(exportOptions)
    const worksheetText = merged.worksheetText
    if (!worksheetText || !hasActiveWorksheetHeader(worksheetText)) {
      return null
    }
    const topic = resolveWorksheetTopicText(worksheetText, getTitle())
    try {
      return await captureWorksheetHeader(topic, worksheetText, worksheetHeaderLabels())
    } catch (error) {
      console.error('[worksheetHeader] Failed to capture header for PDF:', error)
      notify.warningKey('canvas.worksheetText.headerCaptureFailed')
      return null
    }
  }

  function resolvePdfOrientation(
    format: string,
    container: HTMLElement,
    exportOptions?: CanvasExportOptions,
    capture?: Pick<PdfRasterCapture, 'width' | 'height'>
  ): PdfPageOrientation {
    const width = capture?.width ?? container.clientWidth
    const height = capture?.height ?? container.clientHeight
    return resolvePdfOrientationFromExportOptions(format, width, height, exportOptions?.layout)
  }

  async function capturePngBlob(
    exportOptions?: CanvasExportOptions,
    asShown = false
  ): Promise<Blob> {
    const container = getContainer()
    if (!container) {
      throw new Error('canvas-not-ready')
    }
    await waitForExportFonts()
    const captureOptions = getDiagramCanvasHtmlToImageOptions()
    const runCapture = async () => {
      const canvas = await captureDiagramRasterCanvas(container, captureOptions)
      applyLlmExportWatermarkToCanvas(
        canvas,
        diagramStore.data as Record<string, unknown> | null,
        (key) => t(key),
        uiStore.language
      )
      return canvasToPngBlob(canvas)
    }
    const blob = asShown
      ? await runAsShownRasterCapture(runCapture)
      : await runLearningSheetRasterCapture(diagramStore, exportOptions, runCapture)
    if (!blob || blob.size === 0) {
      throw new Error('PNG export produced empty image')
    }
    return blob
  }

  function downloadPngBlob(blob: Blob): Promise<DeliverExportResult> {
    return deliverExportFile(blob, exportFilename(getTitle(), 'png'))
  }

  function notifyCanvasNotReady(error: unknown): boolean {
    if (error instanceof Error && error.message === 'canvas-not-ready') {
      notify.warningKey('canvas.export.canvasNotReady')
      return true
    }
    return false
  }

  async function exportAsPng(exportOptions?: CanvasExportOptions): Promise<void> {
    isExporting.value = true
    try {
      const blob = await capturePngBlob(exportOptions)
      if ((await downloadPngBlob(blob)) === 'cancelled') return
      logDiagramExport('png')
      notify.successKey('canvas.export.pngSuccess')
    } catch (error) {
      if (notifyCanvasNotReady(error)) {
        return
      }
      console.error('PNG export failed:', error)
      notify.errorKey('canvas.export.pngError')
    } finally {
      isExporting.value = false
    }
  }

  async function copyPngToClipboard(blobSource: Promise<Blob>): Promise<void> {
    if (isExporting.value) {
      return
    }
    isExporting.value = true
    try {
      let sharedFile = false
      const outcome = await copyPngBlobWithFallback(blobSource, async (blob) => {
        const delivery = await downloadPngBlob(blob)
        if (delivery === 'cancelled') {
          throw new Error('export-share-cancelled')
        }
        sharedFile = delivery === 'shared'
      })
      if (outcome === 'copied') {
        logDiagramExport('clipboard')
        notify.successKey('notification.copied')
        return
      }
      logDiagramExport('png')
      if (sharedFile) {
        notify.successKey('canvas.export.pngSuccess')
        return
      }
      notify.warningKey('canvas.export.clipboardFallback')
    } catch (error) {
      if (error instanceof Error && error.message === 'export-share-cancelled') {
        return
      }
      if (notifyCanvasNotReady(error)) {
        return
      }
      console.error('Clipboard export failed:', error)
      notify.errorKey('notification.copyFailed')
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsSvg(exportOptions?: CanvasExportOptions): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warningKey('canvas.export.canvasNotReady')
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()

      const filename = exportFilename(getTitle(), 'svg')
      let delivered: DeliverExportResult
      if (canUseMindMapVectorExport(diagramStore)) {
        // Write the markup itself. A data: URL would have to be fetched to become
        // a file, and production connect-src does not allow data:.
        const vector = await runLearningSheetRasterCapture(diagramStore, exportOptions, () =>
          captureMindMapVectorSvg()
        )
        delivered = await deliverExportFile(
          new Blob([vector.svg], { type: 'image/svg+xml' }),
          filename
        )
      } else {
        const { toSvg } = await loadHtmlToImageModule()
        const captureOptions = getDiagramCanvasHtmlToImageOptions()
        const dataUrl = await runLearningSheetRasterCapture(diagramStore, exportOptions, () =>
          toSvg(container, captureOptions)
        )
        delivered = await deliverExportDataUrl(dataUrl, filename)
      }

      if (delivered === 'cancelled') return

      logDiagramExport('svg')
      notify.successKey('canvas.export.svgSuccess')
    } catch (error) {
      console.error('SVG export failed:', error)
      notify.errorKey('canvas.export.svgError')
    } finally {
      isExporting.value = false
    }
  }

  async function captureMindMapVectorSvg(): Promise<MindMapVectorSvgResult> {
    const result = buildMindMapVectorSvgFromStores(diagramStore, uiStore)
    if (!result) {
      throw new Error('Mind-map vector snapshot unavailable')
    }
    return result
  }

  async function exportLearningSheetPdf(
    container: HTMLElement,
    orientation: PdfPageOrientation,
    format: string,
    exportOptions?: CanvasExportOptions
  ): Promise<void> {
    const includeAnswers = exportOptions?.answerMode !== 'exclude'
    const savedShowAnswers = diagramStore.learningSheetShowAnswers
    diagramStore.setLearningSheetShowAnswers(false)
    await waitForExportCanvasPaint()

    try {
      if (canUseMindMapVectorExport(diagramStore)) {
        const vectors: MindMapVectorSvgResult[] = [await captureMindMapVectorSvg()]
        if (includeAnswers) {
          const answerVector = await diagramStore.runWithLearningSheetAnswersRevealed(async () => {
            await waitForExportCanvasPaint()
            return captureMindMapVectorSvg()
          })
          vectors.push(answerVector)
        }
        const headerCapture = await resolveWorksheetHeaderCapture(exportOptions)
        const pdf = await exportMindMapVectorPdfDocument({
          orientation,
          vectors,
          headerCapture,
          exportOptions,
        })
        const filename = exportFilename(getTitle(), 'pdf')
        if (!(await handOffPdf(pdf, filename))) return
        logDiagramExport(format)
        notify.successKey('canvas.export.pdfSuccess')
        return
      }

      const worksheetCapture = await captureContainerForPdfRaw(container)
      const captures: PdfRasterCapture[] = [worksheetCapture]

      if (includeAnswers) {
        const answerCapture = await diagramStore.runWithLearningSheetAnswersRevealed(async () => {
          await waitForExportCanvasPaint()
          return captureContainerForPdfRaw(container)
        })
        captures.push(answerCapture)
      }

      const headerCapture = await resolveWorksheetHeaderCapture(exportOptions)
      const pdf = await buildA4PdfFromImages(captures, orientation, headerCapture, exportOptions)
      const filename = exportFilename(getTitle(), 'pdf')
      if (!(await handOffPdf(pdf, filename))) return

      logDiagramExport(format)
      notify.successKey('canvas.export.pdfSuccess')
    } finally {
      diagramStore.setLearningSheetShowAnswers(savedShowAnswers)
    }
  }

  async function exportAsPdf(format: string, exportOptions?: CanvasExportOptions): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warningKey('canvas.export.canvasNotReady')
      return
    }

    const mergedOptions = resolveExportOptions(exportOptions)

    isExporting.value = true
    try {
      await waitForExportFonts()

      if (isLearningSheetRasterCapture(diagramStore)) {
        const orientation = resolvePdfOrientation(format, container, mergedOptions)
        await exportLearningSheetPdf(container, orientation, format, mergedOptions)
        return
      }

      if (canUseMindMapVectorExport(diagramStore)) {
        await waitForExportCanvasPaint()
        const vector = await captureMindMapVectorSvg()
        const orientation = resolvePdfOrientation(format, container, mergedOptions, {
          width: vector.width,
          height: vector.height,
        })
        const headerCapture = await resolveWorksheetHeaderCapture(mergedOptions)
        const pdf = await exportMindMapVectorPdfDocument({
          orientation,
          vectors: [vector],
          headerCapture,
          exportOptions: mergedOptions,
        })
        const filename = exportFilename(getTitle(), 'pdf')
        if (!(await handOffPdf(pdf, filename))) return
        logDiagramExport(format)
        notify.successKey('canvas.export.pdfSuccess')
        return
      }

      const capture = await captureContainerForPdf(container, mergedOptions)
      const orientation = resolvePdfOrientation(format, container, mergedOptions, capture)
      const headerCapture = await resolveWorksheetHeaderCapture(mergedOptions)
      const pdf = await buildA4PdfFromImages([capture], orientation, headerCapture, mergedOptions)
      const filename = exportFilename(getTitle(), 'pdf')
      if (!(await handOffPdf(pdf, filename))) return
      logDiagramExport(format)
      notify.successKey('canvas.export.pdfSuccess')
    } catch (error) {
      console.error('PDF export failed:', error)
      notify.errorKey('canvas.export.pdfError')
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsMgFile(): Promise<void> {
    const spec = getDiagramSpec()
    if (!spec) {
      notify.warningKey('canvas.export.noDiagramData')
      return
    }

    isExporting.value = true
    try {
      const json = JSON.stringify(spec)
      const bytes = await encodeMgFileContents(json, specHasSecondaryText(spec) ? '2.0' : '1.1')
      const blob = new Blob([new Uint8Array(bytes)], { type: 'application/octet-stream' })
      if (!(await handOffExportFile(blob, exportFilename(getTitle(), 'mg')))) return

      logDiagramExport('mg')
      notify.successKey('canvas.export.jsonSuccess')
    } catch (error) {
      console.error('MG export failed:', error)
      notify.errorKey('canvas.export.jsonError')
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsWorksheetDocx(exportOptions?: CanvasExportOptions): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warningKey('canvas.export.canvasNotReady')
      return
    }

    const mergedOptions = resolveExportOptions(exportOptions)
    const worksheetText = mergedOptions.worksheetText
    if (!worksheetText) {
      notify.warningKey('canvas.export.docxError')
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()
      let diagramBlob: Blob
      if (canUseMindMapVectorExport(diagramStore)) {
        const raster = await runLearningSheetRasterCapture(diagramStore, mergedOptions, () =>
          exportMindMapVectorDocxPng(diagramStore, uiStore)
        )
        if (!raster) {
          throw new Error('Mind-map vector DOCX raster produced empty PNG')
        }
        diagramBlob = raster.blob
      } else {
        const capture = await captureContainerForPdf(container, mergedOptions)
        diagramBlob = dataUrlToBlob(capture.dataUrl)
      }
      const title = getTitle()
      const formData = new FormData()
      formData.append('diagram', diagramBlob, 'diagram.png')
      formData.append(
        'meta',
        JSON.stringify({
          title,
          layout: mergedOptions.layout,
          showTopic: worksheetText.showTopic,
          showName: worksheetText.showName,
          showClass: worksheetText.showClass,
          showDate: worksheetText.showDate,
          showInstruction: worksheetText.showInstruction,
          topicText: resolveWorksheetTopicText(worksheetText, title),
          instructionText: worksheetText.instructionText,
          diagramOffsetX: worksheetText.diagramOffsetX,
          diagramOffsetY: worksheetText.diagramOffsetY,
          diagramScale: worksheetText.diagramScale,
          labels: {
            name: t('canvas.worksheetText.fieldName'),
            className: t('canvas.worksheetText.fieldClass'),
            date: t('canvas.worksheetText.fieldDate'),
            instructionPrefix: t('canvas.worksheetText.instructionPrefix'),
            defaultInstruction: t('canvas.worksheetText.defaultInstruction'),
          },
        })
      )

      const response = await apiUpload('/api/export_worksheet_docx', formData)
      if (!response.ok) {
        throw new Error(`DOCX export failed (${response.status})`)
      }
      const docxBlob = await response.blob()
      if (!(await handOffExportFile(docxBlob, exportFilename(title, 'docx')))) return
      logDiagramExport('worksheet_docx')
      notify.successKey('canvas.export.docxSuccess')
    } catch (error) {
      console.error('Worksheet DOCX export failed:', error)
      notify.errorKey('canvas.export.docxError')
    } finally {
      isExporting.value = false
    }
  }

  async function exportByFormat(
    format: string,
    exportOptions?: CanvasExportOptions
  ): Promise<void> {
    if (isExporting.value) {
      return
    }
    switch (format) {
      case 'clipboard':
        await copyPngToClipboard(capturePngBlob(exportOptions, true))
        break
      case 'png':
        await exportAsPng(exportOptions)
        break
      case 'svg':
        await exportAsSvg(exportOptions)
        break
      case 'pdf':
      case 'pdf_landscape':
      case 'pdf_portrait':
        await exportAsPdf(format, exportOptions)
        break
      case 'worksheet_docx':
        await exportAsWorksheetDocx(exportOptions)
        break
      case 'mg':
        await exportAsMgFile()
        break
      default:
        if (isPdfExportCommand(format)) {
          await exportAsPdf(format, exportOptions)
          break
        }
        notify.warningKey('canvas.export.unknownFormat', { format })
    }
  }

  return {
    capturePngBlob,
    copyPngToClipboard,
    exportAsPng,
    exportAsSvg,
    exportAsPdf,
    exportAsWorksheetDocx,
    exportAsMgFile,
    exportByFormat,
    isExporting,
  }
}
