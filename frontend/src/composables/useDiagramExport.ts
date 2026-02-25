/**
 * useDiagramExport - Composable for exporting MindGraph diagrams
 * Supports PNG, SVG, PDF (via html-to-image + jspdf), and JSON
 */
import { ref } from 'vue'

import { toPng, toSvg } from 'html-to-image'
import { jsPDF } from 'jspdf'

import { useNotifications } from '@/composables'

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

export interface UseDiagramExportOptions {
  getContainer: () => HTMLElement | null
  getDiagramSpec: () => Record<string, unknown> | null
  getTitle: () => string
  isZh: () => boolean
}

export function useDiagramExport(options: UseDiagramExportOptions) {
  const { getContainer, getDiagramSpec, getTitle, isZh } = options
  const notify = useNotifications()

  const isExporting = ref(false)

  async function exportAsPng(): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(isZh() ? '无法导出：画布未就绪' : 'Cannot export: canvas not ready')
      return
    }

    isExporting.value = true
    try {
      const dataUrl = await toPng(container, {
        backgroundColor: '#ffffff',
        pixelRatio: 2,
        style: { transform: 'none' },
      })

      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownload(dataUrl, `${baseName}_${timestamp}.png`)

      notify.success(isZh() ? 'PNG图片导出成功' : 'PNG exported successfully')
    } catch (error) {
      console.error('PNG export failed:', error)
      notify.error(isZh() ? 'PNG导出失败，请重试' : 'PNG export failed, please try again')
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsSvg(): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(isZh() ? '无法导出：画布未就绪' : 'Cannot export: canvas not ready')
      return
    }

    isExporting.value = true
    try {
      const dataUrl = await toSvg(container, {
        backgroundColor: '#ffffff',
        style: { transform: 'none' },
      })

      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownload(dataUrl, `${baseName}_${timestamp}.svg`)

      notify.success(isZh() ? 'SVG导出成功' : 'SVG exported successfully')
    } catch (error) {
      console.error('SVG export failed:', error)
      notify.error(isZh() ? 'SVG导出失败，请重试' : 'SVG export failed, please try again')
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsPdf(): Promise<void> {
    const container = getContainer()
    if (!container) {
      notify.warning(isZh() ? '无法导出：画布未就绪' : 'Cannot export: canvas not ready')
      return
    }

    isExporting.value = true
    try {
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

      notify.success(isZh() ? 'PDF导出成功' : 'PDF exported successfully')
    } catch (error) {
      console.error('PDF export failed:', error)
      notify.error(isZh() ? 'PDF导出失败，请重试' : 'PDF export failed, please try again')
    } finally {
      isExporting.value = false
    }
  }

  async function exportAsJson(): Promise<void> {
    const spec = getDiagramSpec()
    if (!spec) {
      notify.warning(isZh() ? '没有可导出的图示数据' : 'No diagram data to export')
      return
    }

    isExporting.value = true
    try {
      const json = JSON.stringify(spec, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const baseName = sanitizeFilename(getTitle())
      const timestamp = new Date().toISOString().slice(0, 10)
      triggerDownloadBlob(blob, `${baseName}_${timestamp}.json`)

      notify.success(isZh() ? 'JSON导出成功' : 'JSON exported successfully')
    } catch (error) {
      console.error('JSON export failed:', error)
      notify.error(isZh() ? 'JSON导出失败，请重试' : 'JSON export failed, please try again')
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
          notify.warning(isZh() ? `未知导出格式: ${format}` : `Unknown export format: ${format}`)
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
