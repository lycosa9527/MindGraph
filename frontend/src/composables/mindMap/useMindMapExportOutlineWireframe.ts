import { computed, type ComputedRef } from 'vue'

import type { CSSProperties } from 'vue'

import {
  applyMindMapOutlineWireframeNodeStyle,
  applyMindMapOutlineWireframeUnderlineBar,
} from '@/utils/mindMapOutlineWireframeStyle'
import { useUIStore } from '@/stores/ui'

export function useMindMapExportOutlineWireframeActive(): ComputedRef<boolean> {
  const uiStore = useUIStore()
  return computed(() => uiStore.exportWireframeOutline)
}

export function wrapMindMapNodeStyleForExport(
  style: CSSProperties,
  exportOutlineActive: boolean,
  opts: { isMindMapV2: boolean; isUnderlineShape?: boolean }
): CSSProperties {
  if (!exportOutlineActive || !opts.isMindMapV2) {
    return style
  }
  return applyMindMapOutlineWireframeNodeStyle(style, {
    isUnderline: opts.isUnderlineShape,
  })
}

export function wrapMindMapUnderlineBarForExport(
  style: CSSProperties,
  exportOutlineActive: boolean
): CSSProperties {
  if (!exportOutlineActive) {
    return style
  }
  return applyMindMapOutlineWireframeUnderlineBar(style)
}
