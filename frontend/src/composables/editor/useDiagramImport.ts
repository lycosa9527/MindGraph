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
import { CMAP_PARSE_FAILED, decodeCmapToConceptMapSpec } from '@/utils/cmapImport'
import { MG_FILE_NOT_ENCRYPTED, decodeMgFileToJsonText } from '@/utils/mgInterchange'

function isValidMindGraphEncryptedExport(obj: unknown): obj is Record<string, unknown> {
  if (!obj || typeof obj !== 'object') return false
  const spec = obj as Record<string, unknown>
  const type = spec.type as DiagramType | undefined
  if (!type || !VALID_DIAGRAM_TYPES.includes(type)) return false
  if (!Array.isArray(spec.nodes) || !Array.isArray(spec.connections)) return false
  if (spec.nodes.length === 0) return false
  return true
}

/** Saved `.mg` JSON OR `.cmap` concept-map template (`topic` / `concepts` / `relationships`). */
function isValidImportedDiagramSpec(obj: unknown): obj is Record<string, unknown> {
  if (!obj || typeof obj !== 'object') return false
  const spec = obj as Record<string, unknown>
  const type = spec.type as DiagramType | undefined
  if (!type || !VALID_DIAGRAM_TYPES.includes(type)) return false
  if (type === 'concept_map') {
    const conceptsOk = Array.isArray(spec.concepts)
    const relationshipsOk = Array.isArray(spec.relationships)
    const topicOk = typeof spec.topic === 'string' && spec.topic.length > 0
    if (conceptsOk && relationshipsOk && topicOk) {
      return true
    }
  }
  return isValidMindGraphEncryptedExport(obj)
}

export function useDiagramImport() {
  const route = useRoute()
  const router = useRouter()
  const { t } = useLanguage()
  const notify = useNotifications()

  function triggerImport(): void {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.mg,.cmap'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      const lowerName = file.name.toLowerCase()
      const isMg = lowerName.endsWith('.mg')
      const isCmap = lowerName.endsWith('.cmap')
      if (!isMg && !isCmap) {
        notify.error(t('canvas.import.invalidFile'))
        return
      }
      try {
        const buffer = await file.arrayBuffer()
        let payloadJson: string
        if (isCmap) {
          const spec = decodeCmapToConceptMapSpec(buffer)
          if (!isValidImportedDiagramSpec(spec)) {
            notify.error(t('canvas.import.invalidFile'))
            return
          }
          payloadJson = JSON.stringify(spec)
        } else {
          const text = await decodeMgFileToJsonText(buffer)
          const parsed = JSON.parse(text) as unknown
          if (!isValidImportedDiagramSpec(parsed)) {
            notify.error(t('canvas.import.invalidFile'))
            return
          }
          payloadJson = text
        }
        sessionStorage.setItem(IMPORT_SPEC_KEY, payloadJson)
        router.push({
          path: canvasPathForImportNavigation(route.path),
          query: { import: '1' },
        })
      } catch (error) {
        console.error('Import failed:', error)
        if (error instanceof Error) {
          if (error.message === MG_FILE_NOT_ENCRYPTED) {
            notify.error(t('canvas.import.invalidFile'))
            return
          }
          if (error.message === CMAP_PARSE_FAILED) {
            notify.error(t('canvas.import.invalidFile'))
            return
          }
        }
        notify.error(t('canvas.import.parseError'))
      }
    }
    input.click()
  }

  return { triggerImport }
}
