/**
 * useDiagramImport - Import diagram from encrypted `.mg` file (landing page)
 * Validates spec and stores in sessionStorage for CanvasPage to load
 */
import { useRoute, useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { IMPORT_SPEC_KEY } from '@/config'
import { useDiagramStore } from '@/stores'
import type { DiagramType } from '@/types'
import { canvasPathForImportNavigation } from '@/utils/canvasBackNavigation'
import { CMAP_PARSE_FAILED, decodeCmapToConceptMapSpec } from '@/utils/cmapImport'
import { MG_FILE_NOT_ENCRYPTED, decodeMgFileToJsonText } from '@/utils/mgInterchange'

export type DiagramImportExtension = 'mg' | 'cmap'

const MG_ONLY_IMPORT: readonly DiagramImportExtension[] = ['mg']
const CONCEPT_MAP_IMPORT: readonly DiagramImportExtension[] = ['mg', 'cmap']

function extensionsToAcceptAttr(extensions: readonly DiagramImportExtension[]): string {
  return extensions.map((ext) => `.${ext}`).join(',')
}

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
    const units = spec.concept_units
    const unitsOk =
      Array.isArray(units) &&
      units.length > 0 &&
      units.every(
        (u: unknown) =>
          u !== null &&
          typeof u === 'object' &&
          typeof (u as { id?: unknown }).id === 'string' &&
          typeof (u as { label?: unknown }).label === 'string'
      )
    const relationshipsOk = Array.isArray(spec.relationships)
    const topicOk = typeof spec.topic === 'string' && spec.topic.length > 0
    if (unitsOk && relationshipsOk && topicOk) {
      return true
    }
    const conceptsOkLegacy = Array.isArray(spec.concepts) && spec.concepts.length > 0
    if (conceptsOkLegacy && relationshipsOk && topicOk) {
      return true
    }
    return false
  }
  return isValidMindGraphEncryptedExport(obj)
}

export function useDiagramImport() {
  const route = useRoute()
  const router = useRouter()
  const { t } = useLanguage()
  const notify = useNotifications()
  const diagramStore = useDiagramStore()

  async function parseImportFile(
    file: File,
    allowedExtensions: readonly DiagramImportExtension[]
  ): Promise<Record<string, unknown> | null> {
    const lowerName = file.name.toLowerCase()
    const isMg = lowerName.endsWith('.mg')
    const isCmap = lowerName.endsWith('.cmap')
    const allowedMg = allowedExtensions.includes('mg')
    const allowedCmap = allowedExtensions.includes('cmap')
    if (isCmap && !allowedCmap) {
      notify.error(t('canvas.import.invalidFile'))
      return null
    }
    if (isMg && !allowedMg) {
      notify.error(t('canvas.import.invalidFile'))
      return null
    }
    if (!isMg && !isCmap) {
      notify.error(t('canvas.import.invalidFile'))
      return null
    }
    try {
      const buffer = await file.arrayBuffer()
      if (isCmap) {
        const spec = decodeCmapToConceptMapSpec(buffer)
        if (!isValidImportedDiagramSpec(spec)) {
          notify.error(t('canvas.import.invalidFile'))
          return null
        }
        const cmapHintsRaw = spec._import_hints
        if (Array.isArray(cmapHintsRaw)) {
          cmapHintsRaw.forEach((hintKey) => {
            if (typeof hintKey === 'string') {
              notify.info(t(hintKey))
            }
          })
        }
        return spec
      }
      const text = await decodeMgFileToJsonText(buffer)
      const parsed = JSON.parse(text) as unknown
      if (!isValidImportedDiagramSpec(parsed)) {
        notify.error(t('canvas.import.invalidFile'))
        return null
      }
      return parsed as Record<string, unknown>
    } catch (error) {
      console.error('Import failed:', error)
      if (error instanceof Error) {
        if (error.message === MG_FILE_NOT_ENCRYPTED || error.message === CMAP_PARSE_FAILED) {
          notify.error(t('canvas.import.invalidFile'))
          return null
        }
      }
      notify.error(t('canvas.import.parseError'))
      return null
    }
  }

  /** Import on the canvas page without navigation (toolbar). */
  function triggerImportInPlace(
    allowedExtensions: readonly DiagramImportExtension[] = MG_ONLY_IMPORT
  ): void {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = extensionsToAcceptAttr(allowedExtensions)
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      const spec = await parseImportFile(file, allowedExtensions)
      if (!spec) return
      const diagramType = spec.type as DiagramType
      if (diagramStore.loadFromSpec(spec, diagramType)) {
        notify.success(t('canvas.toolbar.importSuccess'))
      } else {
        notify.error(t('canvas.import.parseError'))
      }
    }
    input.click()
  }

  function triggerConceptMapImportInPlace(): void {
    triggerImportInPlace(CONCEPT_MAP_IMPORT)
  }

  function triggerImport(): void {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = extensionsToAcceptAttr(CONCEPT_MAP_IMPORT)
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      const spec = await parseImportFile(file, CONCEPT_MAP_IMPORT)
      if (!spec) return
      try {
        sessionStorage.setItem(IMPORT_SPEC_KEY, JSON.stringify(spec))
        router.push({
          path: canvasPathForImportNavigation(route.path),
          query: { import: '1' },
        })
      } catch (error) {
        console.error('Import failed:', error)
        notify.error(t('canvas.import.parseError'))
      }
    }
    input.click()
  }

  return { triggerImport, triggerImportInPlace, triggerConceptMapImportInPlace }
}
