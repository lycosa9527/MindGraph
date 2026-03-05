/**
 * Border style utilities for diagram nodes
 * Handles standard CSS border-style and custom patterns (e.g. dash-dot)
 * Uses background-clip for dash-dot patterns so they respect border-radius (pill shapes)
 */

import type { NodeStyle } from '@/types'

export type BorderStyleType =
  | 'solid'
  | 'dashed'
  | 'dotted'
  | 'double'
  | 'dash-dot'
  | 'dash-dot-dot'

const DASH_DOT_GRADIENT = (color: string) =>
  `repeating-linear-gradient(90deg, ${color} 0px, ${color} 10px, transparent 10px, transparent 14px, ${color} 14px, ${color} 16px, transparent 16px, transparent 22px)`

const DASH_DOT_DOT_GRADIENT = (color: string) =>
  `repeating-linear-gradient(90deg, ${color} 0px, ${color} 8px, transparent 8px, transparent 10px, ${color} 10px, ${color} 12px, transparent 12px, transparent 14px, ${color} 14px, ${color} 16px, transparent 16px, transparent 24px)`

export interface BorderStyleOptions {
  /** Required for dash-dot/dash-dot-dot to respect border-radius (pill shapes) */
  backgroundColor?: string
}

/**
 * Returns CSS border properties for a node style.
 * For dash-dot patterns: uses background-clip (not border-image) so border-radius works.
 */
export function getBorderStyleProps(
  borderColor: string,
  borderWidth: number | string,
  borderStyle: BorderStyleType | undefined,
  options?: BorderStyleOptions
): Record<string, string> {
  const width = typeof borderWidth === 'number' ? `${borderWidth}px` : borderWidth
  const style = borderStyle || 'solid'
  const bg = options?.backgroundColor ?? '#ffffff'

  if (style === 'dash-dot') {
    return {
      border: `${width} solid transparent`,
      backgroundImage: `linear-gradient(${bg}, ${bg}), ${DASH_DOT_GRADIENT(borderColor)}`,
      backgroundClip: 'padding-box, border-box',
      backgroundOrigin: 'padding-box, border-box',
    }
  }

  if (style === 'dash-dot-dot') {
    return {
      border: `${width} solid transparent`,
      backgroundImage: `linear-gradient(${bg}, ${bg}), ${DASH_DOT_DOT_GRADIENT(borderColor)}`,
      backgroundClip: 'padding-box, border-box',
      backgroundOrigin: 'padding-box, border-box',
    }
  }

  return {
    borderColor,
    borderWidth: width,
    borderStyle: style,
  }
}

/**
 * Resolves border style from node style, falling back to default.
 */
export function resolveBorderStyle(style?: NodeStyle['borderStyle']): BorderStyleType {
  return style || 'solid'
}
