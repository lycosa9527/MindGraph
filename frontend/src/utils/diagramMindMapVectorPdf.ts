/**
 * Embed vector mind-map SVG into an A4 jsPDF page (real text via svg2pdf).
 */
import {
  collectMindMapVectorPdfSubsetText,
  registerMindMapVectorPdfFonts,
} from '@/utils/diagramMindMapVectorPdfFonts'
import type { MindMapVectorSvgResult } from '@/utils/diagramMindMapVectorSvg'
import {
  type PdfPageOrientation,
  fitImageRectInA4Region,
  fitImageRectOnA4Page,
} from '@/utils/diagramPdfExport'
import {
  type WorksheetDiagramCrop,
  ZERO_WORKSHEET_DIAGRAM_CROP,
  applyWorksheetDiagramCropToSvg,
  worksheetDiagramHasCustomPlacement,
} from '@/utils/worksheetDiagramCrop'

type JsPdfDoc = InstanceType<(typeof import('jspdf'))['jsPDF']> & {
  svg: (
    element: Element,
    options: { x: number; y: number; width: number; height: number }
  ) => Promise<unknown>
}

export type MindMapVectorPdfPageInput = {
  vector: MindMapVectorSvgResult
  headerCapture?: { dataUrl: string; width: number; height: number } | null
  diagramOffsetX?: number
  diagramOffsetY?: number
  diagramScale?: number
  diagramCrop?: WorksheetDiagramCrop
}

function parseSvgElement(svg: string): SVGSVGElement {
  const parser = new DOMParser()
  const doc = parser.parseFromString(svg, 'image/svg+xml')
  const el = doc.documentElement
  if (!(el instanceof SVGSVGElement)) {
    throw new Error('Invalid mind-map vector SVG for PDF')
  }
  return el
}

async function embedSvgOnPage(
  pdf: JsPdfDoc,
  vector: MindMapVectorSvgResult,
  rect: { x: number; y: number; width: number; height: number },
  crop: WorksheetDiagramCrop = ZERO_WORKSHEET_DIAGRAM_CROP
): Promise<void> {
  const cropped = applyWorksheetDiagramCropToSvg(vector.svg, vector.viewBox, crop)
  const svgEl = parseSvgElement(cropped.svg)
  await pdf.svg(svgEl, {
    x: rect.x,
    y: rect.y,
    width: rect.width,
    height: rect.height,
  })
}

/**
 * Build an A4 PDF from one or more vector diagram pages (learning sheet = multi-page).
 */
export async function buildA4PdfFromMindMapVectors(
  pages: MindMapVectorPdfPageInput[],
  orientation: PdfPageOrientation
): Promise<JsPdfDoc> {
  if (pages.length === 0) {
    throw new Error('Mind-map vector PDF requires at least one page')
  }
  const { jsPDF } = await import('jspdf')
  await import('svg2pdf.js')

  const pdf = new jsPDF({
    orientation,
    unit: 'mm',
    format: 'a4',
  })
  const subsetText = collectMindMapVectorPdfSubsetText(pages.map((page) => page.vector.svg))
  await registerMindMapVectorPdfFonts(pdf, subsetText)

  for (let index = 0; index < pages.length; index += 1) {
    const page = pages[index]
    if (index > 0) {
      pdf.addPage('a4', orientation)
    }

    const header = index === 0 ? (page.headerCapture ?? null) : null
    const offsetX = page.diagramOffsetX ?? 0
    const offsetY = page.diagramOffsetY ?? 0
    const scale = page.diagramScale ?? 1
    const crop = page.diagramCrop ?? ZERO_WORKSHEET_DIAGRAM_CROP
    const hasCustomPlacement = worksheetDiagramHasCustomPlacement(offsetX, offsetY, scale, crop)
    const marginMm = 10

    if (header) {
      const pageW = pdf.internal.pageSize.getWidth()
      const headerGapMm = 4
      let regionTopMm = marginMm
      const headerMaxW = pageW - marginMm * 2
      const headerAspect = header.width / Math.max(1, header.height)
      const headerDrawW = headerMaxW
      const headerDrawH = headerDrawW / headerAspect
      pdf.addImage(header.dataUrl, 'PNG', marginMm, regionTopMm, headerDrawW, headerDrawH)
      regionTopMm += headerDrawH + headerGapMm

      const rect = fitImageRectInA4Region(
        pdf,
        page.vector.width,
        page.vector.height,
        regionTopMm,
        marginMm,
        offsetX,
        offsetY,
        scale,
        crop
      )
      await embedSvgOnPage(pdf, page.vector, rect, crop)
    } else if (index === 0 && hasCustomPlacement) {
      const rect = fitImageRectInA4Region(
        pdf,
        page.vector.width,
        page.vector.height,
        marginMm,
        marginMm,
        offsetX,
        offsetY,
        scale,
        crop
      )
      await embedSvgOnPage(pdf, page.vector, rect, crop)
    } else {
      const rect = fitImageRectOnA4Page(pdf, page.vector.width, page.vector.height)
      await embedSvgOnPage(pdf, page.vector, rect)
    }
  }

  return pdf
}
