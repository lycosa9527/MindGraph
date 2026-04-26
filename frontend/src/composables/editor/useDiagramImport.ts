/**
 * useDiagramImport - Import diagram from encrypted `.mg` file (landing page)
 * Validates spec and stores in sessionStorage for CanvasPage to load
 */
import { useRoute, useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { IMPORT_SPEC_KEY } from '@/config'
import type { DiagramType } from '@/types'
import { canvasPathForImportNavigation } from '@/utils/canvasBackNavigation'
import { MG_FILE_NOT_ENCRYPTED, decodeMgFileToJsonText } from '@/utils/mgInterchange'

function isValidDiagramSpec(obj: unknown): obj is Record<string, unknown> {
  if (!obj || typeof obj !== 'object') return false
  const spec = obj as Record<string, unknown>
  const type = spec.type as DiagramType | undefined
  if (!type || !VALID_DIAGRAM_TYPES.includes(type)) return false
  if (!Array.isArray(spec.nodes) || !Array.isArray(spec.connections)) return false
  // Require at least one node so we load via loadGenericSpec (saved format)
  if (spec.nodes.length === 0) return false
  return true
}

export function useDiagramImport() {
  const route = useRoute()
  const router = useRouter()
  const { t } = useLanguage()
  const notify = useNotifications()

  function triggerImport(): void {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.mg'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      const lowerName = file.name.toLowerCase()
      if (!lowerName.endsWith('.mg')) {
        notify.error(t('canvas.import.invalidFile'))
        return
      }
      try {
        const buffer = await file.arrayBuffer()
        const text = await decodeMgFileToJsonText(buffer)
        const parsed = JSON.parse(text) as unknown
        if (!isValidDiagramSpec(parsed)) {
          notify.error(t('canvas.import.invalidFile'))
          return
        }
        sessionStorage.setItem(IMPORT_SPEC_KEY, text)
        router.push({
          path: canvasPathForImportNavigation(route.path),
          query: { import: '1' },
        })
      } catch (error) {
        console.error('Import failed:', error)
        if (error instanceof Error && error.message === MG_FILE_NOT_ENCRYPTED) {
          notify.error(t('canvas.import.invalidFile'))
          return
        }
        notify.error(t('canvas.import.parseError'))
      }
    }
    input.click()
  }

  return { triggerImport }
}
