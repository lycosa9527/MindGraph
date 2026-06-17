import type { CSSProperties } from 'vue'

import { MINDMAP_UNDERLINE_STROKE_WIDTH } from '@/config/mindMapGeometry'
import type { NodeStyle } from '@/types'

export type NodeShape = 'rounded' | 'rectangle' | 'oval' | 'underline'

export const NODE_SHAPE_OPTIONS: NodeShape[] = ['rounded', 'rectangle', 'oval', 'underline']

export function resolveNodeShape(style: NodeStyle | undefined, isMindMap: boolean): NodeShape {
  if (style?.nodeShape) return style.nodeShape
  return isMindMap ? 'rounded' : 'rounded'
}

export function nodeShapeBorderRadius(shape: NodeShape, isMindMap: boolean): string {
  switch (shape) {
    case 'rectangle':
      return '0px'
    case 'oval':
      return '9999px'
    case 'underline':
      return '0px'
    case 'rounded':
    default:
      return isMindMap ? '4.5px' : '8px'
  }
}

export function applyNodeShapeToStyle(
  base: CSSProperties,
  shape: NodeShape,
  borderColor: string,
  isMindMap: boolean
): CSSProperties {
  if (shape !== 'underline') {
    return {
      ...base,
      borderRadius: nodeShapeBorderRadius(shape, isMindMap),
    }
  }

  return {
    ...base,
    backgroundColor: 'transparent',
    borderColor: 'transparent',
    borderWidth: '0px',
    borderStyle: 'none',
    borderRadius: '0px',
    boxShadow: 'none',
  }
}

/** Place vue-flow handles on the underline midline (horizontal branch join). */
export function mindMapUnderlineHandleStyle(side: 'left' | 'right'): CSSProperties {
  const half = MINDMAP_UNDERLINE_STROKE_WIDTH / 2
  const tx = side === 'left' ? '-50%' : '50%'
  return {
    top: 'auto',
    bottom: `${half}px`,
    transform: `translate(${tx}, 50%)`,
  }
}
