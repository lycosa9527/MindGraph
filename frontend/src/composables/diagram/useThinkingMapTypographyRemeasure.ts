import { nextTick, watch, type Ref } from 'vue'

import { useNodeDimensions } from '@/composables/editor/useNodeDimensions'
import { typographyStyleWatchDeps } from '@/stores/diagram/thinkingMapTypographyRelayout'
import type { NodeStyle } from '@/types'

async function remeasureRootBox(reportDimensions: () => void): Promise<void> {
  await nextTick()
  if (typeof document !== 'undefined' && document.fonts?.ready) {
    await document.fonts.ready
  }
  await nextTick()
  reportDimensions()
}

/**
 * Re-run DOM measurement after inline typography changes when ResizeObserver
 * does not fire (decorations, italic, or width locked from the last layout pass).
 */
export function useThinkingMapTypographyRemeasure(options: {
  enabled: () => boolean
  style: () =>
    | Pick<NodeStyle, 'fontSize' | 'fontWeight' | 'fontFamily' | 'fontStyle' | 'textDecoration'>
    | null
    | undefined
  remeasure: () => void | Promise<void>
  afterRemeasure?: () => void
}): void {
  // Compare the font fields, not the style object. Layout rebuilds a new style
  // object on every pass; a fresh array would remeasure and rebuild forever.
  watch(
    () => JSON.stringify(typographyStyleWatchDeps(options.style())),
    () => {
      if (!options.enabled()) return
      void Promise.resolve(options.remeasure()).then(() => {
        options.afterRemeasure?.()
      })
    }
  )
}

/** ResizeObserver-backed hosts: flush root box after inline typography changes. */
export function useThinkingMapNodeBoxTypographyRemeasure(options: {
  rootRef: Ref<HTMLElement | null>
  nodeId: string
  style: () =>
    | Pick<NodeStyle, 'fontSize' | 'fontWeight' | 'fontFamily' | 'fontStyle' | 'textDecoration'>
    | null
    | undefined
  enabled?: () => boolean
}): void {
  const { reportDimensions } = useNodeDimensions(options.rootRef, options.nodeId)
  useThinkingMapTypographyRemeasure({
    enabled: options.enabled ?? (() => true),
    style: options.style,
    remeasure: () => remeasureRootBox(reportDimensions),
  })
}
