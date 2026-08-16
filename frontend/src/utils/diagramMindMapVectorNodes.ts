/**
 * Node shape SVG for mind-map vector export.
 */
import {
  MIND_MAP_GEOMETRY,
  MINDMAP_UNDERLINE_STROKE_WIDTH,
  mindMapBranchFontSize,
  mindMapHorizontalPadding,
} from '@/config/mindMapGeometry'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import type { NodeStyle } from '@/types'
import {
  OUTLINE_WIREFRAME_FILL,
  OUTLINE_WIREFRAME_INK,
} from '@/utils/mindMapOutlineWireframeStyle'
import { renderMindMapSvgText } from '@/utils/diagramMindMapVectorText'

export type MindMapVectorNodeDraw = {
  id: string
  text: string
  /** Un-editable prefix chrome; body wrap excludes this string. */
  numberPrefix?: string
  type: string
  x: number
  y: number
  width: number
  height: number
  style: NodeStyle
}

function resolveColors(
  node: MindMapVectorNodeDraw,
  outlineWireframe: boolean,
  diagramStyleId?: string | null
): { fill: string; stroke: string; textColor: string; strokeWidth: number } {
  const shape = resolveMindMapNodeShape(
    { id: node.id, type: node.type as 'topic' | 'branch', style: node.style },
    diagramStyleId
  )
  if (outlineWireframe) {
    return {
      fill: shape === 'underline' ? 'none' : OUTLINE_WIREFRAME_FILL,
      stroke: OUTLINE_WIREFRAME_INK,
      textColor: OUTLINE_WIREFRAME_INK,
      strokeWidth: Math.max(node.style.borderWidth ?? MIND_MAP_GEOMETRY.borderWidth, 1),
    }
  }
  const isTopic = node.id === 'topic' || node.type === 'topic' || node.type === 'center'
  return {
    fill:
      shape === 'underline'
        ? 'none'
        : (node.style.backgroundColor ??
          (isTopic ? '#EFF6FF' : MIND_MAP_GEOMETRY.leafBackgroundColor)),
    stroke:
      node.style.borderColor ??
      (isTopic ? MIND_MAP_GEOMETRY.topicBorderColor : MIND_MAP_GEOMETRY.defaultBorderColor),
    textColor:
      node.style.textColor ??
      (isTopic ? '#1E3A8A' : MIND_MAP_GEOMETRY.leafTextColor),
    strokeWidth: node.style.borderWidth ?? MIND_MAP_GEOMETRY.borderWidth,
  }
}

function shapePath(
  shape: ReturnType<typeof resolveMindMapNodeShape>,
  x: number,
  y: number,
  w: number,
  h: number,
  radius: number
): string | null {
  if (shape === 'underline') {
    return null
  }
  if (shape === 'oval') {
    const cx = x + w / 2
    const cy = y + h / 2
    return `<ellipse cx="${cx}" cy="${cy}" rx="${w / 2}" ry="${h / 2}"`
  }
  if (shape === 'rectangle') {
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}"`
  }
  const r = Math.min(radius, w / 2, h / 2)
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" ry="${r}"`
}

export function renderMindMapVectorNode(
  node: MindMapVectorNodeDraw,
  options: { diagramStyleId?: string | null; outlineWireframe: boolean }
): string {
  const shape = resolveMindMapNodeShape(
    { id: node.id, type: node.type as 'topic' | 'branch', style: node.style },
    options.diagramStyleId
  )
  const colors = resolveColors(node, options.outlineWireframe, options.diagramStyleId)
  const radius = node.style.borderRadius ?? 10
  const chunks: string[] = []

  if (shape !== 'underline') {
    const open = shapePath(shape, node.x, node.y, node.width, node.height, radius)
    if (open) {
      chunks.push(
        `${open} fill="${colors.fill}" stroke="${colors.stroke}" stroke-width="${colors.strokeWidth}" />`
      )
    }
  }

  const isTopic = node.id === 'topic' || node.type === 'topic' || node.type === 'center'
  const fontSize =
    node.style.fontSize ??
    (isTopic ? MIND_MAP_GEOMETRY.topicFontSize : mindMapBranchFontSize(node.id))
  const fontWeight =
    node.style.fontWeight ?? (isTopic || /\*\*|__/.test(node.text) ? 'bold' : 'normal')
  const paddingX = mindMapHorizontalPadding(shape)
  const paddingY = shape === 'underline' ? 2 : MIND_MAP_GEOMETRY.paddingY
  const textAlign =
    node.style.textAlign ?? (shape === 'underline' ? 'left' : 'center')
  // Vue Flow node width is border-box; canvas text sits inside padding + border.
  const borderWidth = shape === 'underline' ? 0 : colors.strokeWidth

  chunks.push(
    renderMindMapSvgText({
      x: node.x,
      y: node.y,
      width: node.width,
      height: node.height,
      rawText: node.text,
      numberPrefix: node.numberPrefix,
      fontSize,
      fontWeight: fontWeight === 'bold' ? 'bold' : 'normal',
      textColor: colors.textColor,
      textAlign,
      paddingX,
      paddingY,
      borderWidth,
      role: isTopic ? 'topic' : 'branch',
      underline: shape === 'underline',
    })
  )

  // Topic underline bar (branches draw bar with their incoming edge)
  if (shape === 'underline' && isTopic) {
    const y = node.y + node.height - MINDMAP_UNDERLINE_STROKE_WIDTH / 2
    chunks.push(
      `<path d="M ${node.x} ${y} L ${node.x + node.width} ${y}" fill="none" ` +
        `stroke="${colors.stroke}" stroke-width="${MINDMAP_UNDERLINE_STROKE_WIDTH}" ` +
        `stroke-linecap="butt" />`
    )
  }

  return chunks.join('')
}
