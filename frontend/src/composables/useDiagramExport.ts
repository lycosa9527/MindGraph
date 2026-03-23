/**
 * useDiagramExport - Composable for exporting MindGraph diagrams
 * Supports PNG, SVG, PDF (via html-to-image + jspdf), and JSON
 */
import { ref } from 'vue'

import { toPng, toSvg } from 'html-to-image'
import { jsPDF } from 'jspdf'

import { useNotifications } from '@/composables'
import { useLanguage } from '@/composables/useLanguage'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { useUIStore } from '@/stores/ui'
import { apiRequest } from '@/utils/apiClient'

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
  apiRequest('/api/activity/diagram_export', {
    method: 'POST',
    body: JSON.stringify({ format }),
  }).catch(() => {
    /* Fire-and-forget; do not fail export if log fails */
  })
}

export interface UseDiagramExportOptions {
  getContainer: () => HTMLElement | null
  getDiagramSpec: () => Record<string, unknown> | null
  getTitle: () => string
}

export function useDiagramExport(options: UseDiagramExportOptions) {
  const { getContainer, getDiagramSpec, getTitle } = options
  const { t } = useLanguage()
  const notify = useNotifications()
  const uiStore = useUIStore()

  const isExporting = ref(false)

  async function waitForExportFonts(): Promise<void> {
    await ensureFontsForLanguageCode(uiStore.promptLanguage)
    if (typeof document !== 'undefined' && document.fonts?.ready) {
      await document.fonts.ready
    }
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
      const dataUrl = await toPng(container, {
        backgroundColor: '#ffffff',
        pixelRatio: 2,
        style: { transform: 'none' },
      })

      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownload(dataUrl, `${baseName}_${timestamp}.png`)

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
      const dataUrl = await toSvg(container, {
        backgroundColor: '#ffffff',
        style: { transform: 'none' },
      })

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

  async function exportAsPdf(): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(t('canvas.export.canvasNotReady'))
      return
    }

    isExporting.value = true
    try {
      await waitForExportFonts()
      const dataUrl = await toPng(container, {
        backgroundColor: '#ffffff',
        pixelRatio: 1,
        style: { transform: 'none' },
      })

      const img = new Image()
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve()
        img.onerror = reject
        img.src = dataUrl
      })

      const pdf = new jsPDF({
        orientation: img.width > img.height ? 'landscape' : 'portrait',
        unit: 'px',
        format: [img.width, img.height],
      })

      pdf.addImage(dataUrl, 'PNG', 0, 0, img.width, img.height)
      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      pdf.save(`${baseName}_${timestamp}.pdf`)

      logDiagramExport('pdf')
      notify.success(t('canvas.export.pdfSuccess'))
    } catch (error) {
      console.error('PDF export failed:', error)
      notify.error(t('canvas.export.pdfError'))
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsJson(): Promise<void> {
    const spec = getDiagramSpec()
    if (!spec) {
      notify.warning(t('canvas.export.noDiagramData'))
      return
    }

    isExporting.value = true
    try {
      const json = JSON.stringify(spec, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownloadBlob(blob, `${baseName}_${timestamp}.json`)

      logDiagramExport('json')
      notify.success(t('canvas.export.jsonSuccess'))
    } catch (error) {
      console.error('JSON export failed:', error)
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
        await exportAsPdf()
        break
      case 'json':
        await exportAsJson()
        break
      default:
        notify.warning(t('canvas.export.unknownFormat', { format }))
    }
  }

  return {
    exportAsPng,
    exportAsSvg,
    exportAsPdf,
    exportAsJson,
    exportByFormat,
    isExporting,
  }
}
