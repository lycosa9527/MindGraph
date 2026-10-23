/**
 * Load webfonts for font-menu faces already stored on the open diagram.
 * Phones do not have SimSun / KaiTi / Inter / Space Grotesk installed.
 */
import { watch } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { diagramFontTokensInUse, ensureDiagramCanvasFonts } from '@/fonts/diagramCanvasFonts'

export function useDiagramCanvasFontFaces(): void {
  const diagramStore = useDiagramSession()
  watch(
    () => diagramFontTokensInUse(diagramStore.data).join('\n'),
    (key) => {
      if (!key) return
      void ensureDiagramCanvasFonts(key.split('\n'))
    },
    { immediate: true }
  )
}
