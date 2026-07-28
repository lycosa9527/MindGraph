import type { InjectionKey, Ref } from 'vue'

import type { MindMapCanvasMode } from '@/stores/ui'

/**
 * When set by MindMapLegacyCanvas / MindMapV2Canvas, locks mind-map rendering to one
 * variant for the mounted canvas shell (lazy-loaded split). Null = resolve from store.
 */
export const MIND_MAP_CANVAS_VARIANT_KEY: InjectionKey<Ref<MindMapCanvasMode | null>> =
  Symbol('mindMapCanvasVariant')
