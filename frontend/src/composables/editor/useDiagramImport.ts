/**
 * useDiagramImport - Import diagram from encrypted `.mg` / `.cmap`, or hand-drawn photo
 * Validates spec and stores in sessionStorage for CanvasPage to load
 */
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { prepareConversationImageCapture } from '@/composables/kitty/prepareConversationImageCapture'
import { processConversationImageUpload } from '@/composables/kitty/processConversationImageUpload'
import { IMPORT_SPEC_KEY } from '@/config'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { splitSavedLlmResultsFromSpec } from '@/stores/llmResultsPersist'
import type { DiagramType } from '@/types'
import { canvasPathForImportNavigation } from '@/utils/canvasBackNavigation'
import { CMAP_PARSE_FAILED, decodeCmapToConceptMapSpec } from '@/utils/cmapImport'
import { MG_FILE_NOT_ENCRYPTED, decodeMgFileToJsonText } from '@/utils/mgInterchange'
import { mergeMindMapPresentationExtrasIntoSpec } from '@/utils/mindMapLiveSpecExtras'

const HANDDRAWN_IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp'

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

/** Load an imported spec. Model slots stay in the model menu, not on the canvas body. */
export function loadImportedDiagramSpec(spec: Record<string, unknown>): boolean {
  const diagramType = spec.type as DiagramType
  const { specForLoad, saved } = splitSavedLlmResultsFromSpec(spec)
  const loaded = useDiagramStore().loadFromSpec(specForLoad, diagramType)
  if (!loaded) return false
  const llmResultsStore = useLLMResultsStore()
  if (saved) {
    llmResultsStore.restoreFromSaved(saved, diagramType, specForLoad)
  } else {
    llmResultsStore.clearCache()
  }
  return true
}

export function useDiagramImport() {
  const route = useRoute()
  const router = useRouter()
  const notify = useNotifications()
  const { promptLanguage } = useLanguage()
  const handdrawnImportBusy = ref(false)

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
      notify.errorKey('canvas.import.invalidFile')
      return null
    }
    if (isMg && !allowedMg) {
      notify.errorKey('canvas.import.invalidFile')
      return null
    }
    if (!isMg && !isCmap) {
      notify.errorKey('canvas.import.invalidFile')
      return null
    }
    try {
      const buffer = await file.arrayBuffer()
      if (isCmap) {
        const spec = decodeCmapToConceptMapSpec(buffer)
        if (!isValidImportedDiagramSpec(spec)) {
          notify.errorKey('canvas.import.invalidFile')
          return null
        }
        const cmapHintsRaw = spec._import_hints
        if (Array.isArray(cmapHintsRaw)) {
          cmapHintsRaw.forEach((hintKey) => {
            if (typeof hintKey === 'string') {
              notify.infoKey(hintKey)
            }
          })
        }
        return spec
      }
      const text = await decodeMgFileToJsonText(buffer)
      const parsed = JSON.parse(text) as unknown
      if (!isValidImportedDiagramSpec(parsed)) {
        notify.errorKey('canvas.import.invalidFile')
        return null
      }
      return parsed as Record<string, unknown>
    } catch (error) {
      console.error('Import failed:', error)
      if (error instanceof Error) {
        if (error.message === MG_FILE_NOT_ENCRYPTED || error.message === CMAP_PARSE_FAILED) {
          notify.errorKey('canvas.import.invalidFile')
          return null
        }
      }
      notify.errorKey('canvas.import.parseError')
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
      if (loadImportedDiagramSpec(spec)) {
        notify.successKey('canvas.toolbar.importSuccess')
      } else {
        notify.errorKey('canvas.import.parseError')
      }
    }
    input.click()
  }

  function triggerConceptMapImportInPlace(): void {
    triggerImportInPlace(CONCEPT_MAP_IMPORT)
  }

  /**
   * Hand-drawn / photographed mind map → vision rebuild → editable canvas.
   * Canvas-only: no library save or Document Summary required.
   */
  async function importHanddrawnFile(file: File): Promise<boolean> {
    const prepared = prepareConversationImageCapture(file)
    if (!prepared.ok) {
      if (prepared.reason === 'invalid_type') {
        notify.errorKey('canvas.toolbar.importHanddrawnInvalidType')
      } else if (prepared.reason === 'too_large') {
        notify.errorKey('canvas.toolbar.importHanddrawnTooLarge')
      }
      return false
    }

    if (handdrawnImportBusy.value) return false
    handdrawnImportBusy.value = true
    notify.infoKey('canvas.toolbar.importHanddrawnProgress')

    try {
      const result = await processConversationImageUpload({
        file: prepared.file,
        language: promptLanguage.value,
        applyToLibrary: false,
      })

      if (result.mode === 'handdrawn' && result.spec) {
        const diagramStore = useDiagramStore()
        const loaded = diagramStore.loadFromSpec(
          mergeMindMapPresentationExtrasIntoSpec(
            result.spec,
            diagramStore.data as Record<string, unknown> | null
          ),
          'mindmap'
        )
        if (!loaded) {
          notify.errorKey('canvas.toolbar.importHanddrawnFailed')
          return false
        }
        useLLMResultsStore().reset()
        notify.successKey('canvas.toolbar.importHanddrawnSuccess')
        return true
      }

      notify.infoKey('canvas.toolbar.importHanddrawnNotDetected')
      return false
    } catch (error) {
      console.error('Hand-drawn import failed:', error)
      const message = error instanceof Error ? error.message : ''
      if (/no hand-drawn mind map detected/i.test(message)) {
        notify.infoKey('canvas.toolbar.importHanddrawnNotDetected')
      } else if (/unauthorized|QWEN_API_KEY|DashScope/i.test(message)) {
        notify.errorKey('canvas.toolbar.importHanddrawnApiUnauthorized')
      } else if (message && message !== 'Image processing failed') {
        notify.error(message)
      } else {
        notify.errorKey('canvas.toolbar.importHanddrawnFailed')
      }
      return false
    } finally {
      handdrawnImportBusy.value = false
    }
  }

  function triggerHanddrawnImportInPlace(): void {
    if (handdrawnImportBusy.value) return
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = HANDDRAWN_IMAGE_ACCEPT
    input.onchange = () => {
      const file = input.files?.[0]
      if (!file) return
      void importHanddrawnFile(file)
    }
    input.click()
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
        notify.errorKey('canvas.import.parseError')
      }
    }
    input.click()
  }

  return {
    handdrawnImportBusy,
    triggerImport,
    triggerImportInPlace,
    triggerConceptMapImportInPlace,
    triggerHanddrawnImportInPlace,
  }
}
