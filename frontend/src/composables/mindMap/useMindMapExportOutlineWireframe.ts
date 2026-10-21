import { type ComputedRef, computed } from 'vue'
import type { CSSProperties } from 'vue'

import { useUIStore } from '@/stores/ui'
import {
  applyMindMapOutlineWireframeNodeStyle,
  applyMindMapOutlineWireframeUnderlineBar,
} from '@/utils/mindMapOutlineWireframeStyle'

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
