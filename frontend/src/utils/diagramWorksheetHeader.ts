/**
 * Classroom worksheet header — HTML build + raster capture for PDF export.
 */
import {
  hasActiveWorksheetHeader,
  type CanvasWorksheetTextOptions,
} from '@/config/canvasWorksheetText'
import { loadHtmlToImageModule } from '@/utils/diagramExportHtmlToImage'
import type { DiagramRasterCapture } from '@/utils/diagramExportRasterCapture'
import { loadImageElement } from '@/utils/diagramPdfExport'
import type { HtmlToImageOptions } from '@/utils/diagramHtmlToImage'

export interface WorksheetHeaderLabels {
  name: string
  className: string
  date: string
  instructionPrefix: string
  defaultInstruction: string
}

const HEADER_CAPTURE_WIDTH_PX = 900

function worksheetHeaderCaptureOptions(): HtmlToImageOptions {
  return {
    backgroundColor: '#ffffff',
    pixelRatio: 2,
    style: {
      transform: 'none',
    },
  }
}

function appendUnderlineField(parent: HTMLElement, label: string, minWidthPx: number): void {
  const field = document.createElement('span')
  field.style.display = 'inline-flex'
  field.style.alignItems = 'flex-end'
  field.style.gap = '6px'
  field.style.fontSize = '14px'
  field.style.lineHeight = '1.4'
  field.style.color = '#1c1917'

  const labelEl = document.createElement('span')
  labelEl.textContent = label
  labelEl.style.flexShrink = '0'
  field.appendChild(labelEl)

  const line = document.createElement('span')
  line.style.display = 'inline-block'
  line.style.minWidth = `${minWidthPx}px`
  line.style.borderBottom = '1px solid #44403c'
  line.style.height = '1.25em'
  field.appendChild(line)

  parent.appendChild(field)
}

export function buildWorksheetHeaderElement(
  topicName: string,
  options: CanvasWorksheetTextOptions,
  labels: WorksheetHeaderLabels
): HTMLElement | null {
  if (!hasActiveWorksheetHeader(options)) return null

  const root = document.createElement('div')
  root.setAttribute('data-worksheet-header', 'true')
  root.style.boxSizing = 'border-box'
  root.style.width = `${HEADER_CAPTURE_WIDTH_PX}px`
  root.style.padding = '12px 16px 10px'
  root.style.background = '#ffffff'
  root.style.fontFamily =
    "'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif"
  root.style.color = '#1c1917'

  if (options.showTopic && topicName.trim()) {
    const title = document.createElement('div')
    title.textContent = topicName.trim()
    title.style.textAlign = 'center'
    title.style.fontSize = '20px'
    title.style.fontWeight = '700'
    title.style.lineHeight = '1.35'
    title.style.marginBottom = '12px'
    root.appendChild(title)
  }

  const metaFields = [options.showName, options.showClass, options.showDate].filter(Boolean).length
  if (metaFields > 0) {
    const metaRow = document.createElement('div')
    metaRow.style.display = 'flex'
    metaRow.style.flexWrap = 'wrap'
    metaRow.style.alignItems = 'flex-end'
    metaRow.style.justifyContent = 'space-between'
    metaRow.style.gap = '12px 24px'
    metaRow.style.marginBottom = options.showInstruction ? '10px' : '0'

    if (options.showName) {
      appendUnderlineField(metaRow, labels.name, 120)
    }
    if (options.showClass) {
      appendUnderlineField(metaRow, labels.className, 100)
    }
    if (options.showDate) {
      appendUnderlineField(metaRow, labels.date, 120)
    }

    root.appendChild(metaRow)
  }

  if (options.showInstruction) {
    const instruction = document.createElement('div')
    instruction.style.fontSize = '13px'
    instruction.style.lineHeight = '1.5'
    instruction.style.color = '#44403c'
    const body = options.instructionText.trim() || labels.defaultInstruction
    instruction.textContent = `${labels.instructionPrefix}${body}`
    root.appendChild(instruction)
  }

  return root
}

export async function captureWorksheetHeader(
  topicName: string,
  options: CanvasWorksheetTextOptions,
  labels: WorksheetHeaderLabels
): Promise<DiagramRasterCapture | null> {
  const element = buildWorksheetHeaderElement(topicName, options, labels)
  if (!element) return null

  element.style.position = 'fixed'
  element.style.left = '-10000px'
  element.style.top = '0'
  element.style.zIndex = '-1'
  document.body.appendChild(element)

  try {
    const { toCanvas } = await loadHtmlToImageModule()
    const canvas = await toCanvas(element, worksheetHeaderCaptureOptions())
    const dataUrl = canvas.toDataURL('image/png')
    const image = await loadImageElement(dataUrl)
    return {
      dataUrl,
      width: canvas.width,
      height: canvas.height,
      image,
    }
  } finally {
    element.remove()
  }
}
