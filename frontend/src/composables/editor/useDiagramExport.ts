/**
 * useDiagramExport - Composable for exporting MindGraph diagrams
 * Supports PNG, SVG, PDF (via html-to-image + jspdf), and MG interchange
 */
import { ref } from 'vue'

import { applyThinkingCoinMutation, extractThinkingCoinsFooter } from '@/composables/auth/useThinkingCoinSync'
import { useNotifications } from '@/composables'
import { useLanguage } from '@/composables/core/useLanguage'
import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import {
  hasActiveWorksheetHeader,
  resolveWorksheetTopicText,
} from '@/config/canvasWorksheetText'
import { mergeCanvasExportOptions } from '@/utils/mergeCanvasExportOptions'
import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'
import { apiRequestJson, apiUpload } from '@/utils/apiClient'
import { loadHtmlToImageModule } from '@/utils/diagramExportHtmlToImage'
import {
  isLearningSheetRasterCapture,
  runLearningSheetRasterCapture,
  waitForExportCanvasPaint,
} from '@/utils/diagramExportLearningSheet'
import { waitForDiagramExportFonts } from '@/utils/diagramExportPrep'
import {
  captureDiagramPngBlob,
  captureDiagramPngData,
  type DiagramRasterCapture,
} from '@/utils/diagramExportRasterCapture'
import {
  getDiagramCanvasHtmlToImageOptions,
  getDiagramCanvasPdfHtmlToImageOptions,
} from '@/utils/diagramHtmlToImage'
import {
  addRasterImageToA4PdfPage,
  addWorksheetPageToPdf,
  compressRasterDataUrlForA4Pdf,
  isPdfExportCommand,
  resolvePdfOrientationFromExportOptions,
  type PdfPageOrientation,
} from '@/utils/diagramPdfExport'
import {
  captureWorksheetHeader,
  type WorksheetHeaderLabels,
} from '@/utils/diagramWorksheetHeader'
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
    const hasCustomPlacement =
      diagramOffsetX !== 0 || diagramOffsetY !== 0 || diagramScale !== 1
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
      notify.warning(t('canvas.worksheetText.headerCaptureFailed'))
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

  async function exportAsPng(exportOptions?: CanvasExportOptions): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()
      const captureOptions = getDiagramCanvasHtmlToImageOptions()

      const blob = await runLearningSheetRasterCapture(diagramStore, exportOptions, () =>
        captureDiagramPngBlob(container, captureOptions)
      )

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

  async function exportAsSvg(exportOptions?: CanvasExportOptions): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()
      const { toSvg } = await loadHtmlToImageModule()
      const captureOptions = getDiagramCanvasHtmlToImageOptions()

      const dataUrl = await runLearningSheetRasterCapture(diagramStore, exportOptions, () =>
        toSvg(container, captureOptions)
      )

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
    format: string,
    exportOptions?: CanvasExportOptions
  ): Promise<void> {
    const includeAnswers = exportOptions?.answerMode !== 'exclude'
    const savedShowAnswers = diagramStore.learningSheetShowAnswers
    diagramStore.setLearningSheetShowAnswers(false)
    await waitForExportCanvasPaint()

    const worksheetCapture = await captureContainerForPdfRaw(container)
    const captures: PdfRasterCapture[] = [worksheetCapture]

    if (includeAnswers) {
      const answerCapture = await diagramStore.runWithLearningSheetAnswersRevealed(async () => {
        await waitForExportCanvasPaint()
        return captureContainerForPdfRaw(container)
      })
      captures.push(answerCapture)
    }

    diagramStore.setLearningSheetShowAnswers(savedShowAnswers)

    const headerCapture = await resolveWorksheetHeaderCapture(exportOptions)
    const pdf = await buildA4PdfFromImages(captures, orientation, headerCapture, exportOptions)
    const baseName = sanitizeFilename(getTitle())
    const timestamp = new Date().toISOString().slice(0, 10)
    pdf.save(`${baseName}_${timestamp}.pdf`)

    logDiagramExport(format)
    notify.success(t('canvas.export.pdfSuccess'))
  }

  async function exportAsPdf(format: string, exportOptions?: CanvasExportOptions): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
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

      const capture = await captureContainerForPdf(container, mergedOptions)
      const orientation = resolvePdfOrientation(format, container, mergedOptions, capture)
      const headerCapture = await resolveWorksheetHeaderCapture(mergedOptions)
      const pdf = await buildA4PdfFromImages([capture], orientation, headerCapture, mergedOptions)
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

  async function exportAsWorksheetDocx(exportOptions?: CanvasExportOptions): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
      return
    }

    const mergedOptions = resolveExportOptions(exportOptions)
    const worksheetText = mergedOptions.worksheetText
    if (!worksheetText) {
      notify.warning(t('canvas.export.docxError'))
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()
      const capture = await captureContainerForPdf(container, mergedOptions)
      const imageResponse = await fetch(capture.dataUrl)
      const diagramBlob = await imageResponse.blob()
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
      const baseName = sanitizeFilename(title)
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownloadBlob(docxBlob, `${baseName}_${timestamp}.docx`)
      logDiagramExport('worksheet_docx')
      notify.success(t('canvas.export.docxSuccess'))
    } catch (error) {
      console.error('Worksheet DOCX export failed:', error)
      notify.error(t('canvas.export.docxError'))
    } finally {
      isExporting.value = false
    }
  }

  async function exportByFormat(format: string, exportOptions?: CanvasExportOptions): Promise<void> {
    if (isExporting.value) {
      return
    }
    switch (format) {
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
        notify.warning(t('canvas.export.unknownFormat', { format }))
    }
  }

  return {
    exportAsPng,
    exportAsSvg,
    exportAsPdf,
    exportAsWorksheetDocx,
    exportAsMgFile,
    exportByFormat,
    isExporting,
  }
}
