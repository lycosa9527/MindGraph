/**
 * useDiagramImport - Import diagram from JSON file (landing page)
 * Validates spec and stores in sessionStorage for CanvasPage to load
 */
import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { IMPORT_SPEC_KEY } from '@/config'

const VALID_DIAGRAM_TYPES: string[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'mindmap',
  'mind_map',
  'concept_map',
]

function isValidDiagramSpec(obj: unknown): obj is Record<string, unknown> {
  if (!obj || typeof obj !== 'object') return false
  const spec = obj as Record<string, unknown>
  const type = spec.type as string | undefined
  if (!type || !VALID_DIAGRAM_TYPES.includes(type)) return false
  if (!Array.isArray(spec.nodes) || !Array.isArray(spec.connections)) return false
  // Require at least one node so we load via loadGenericSpec (saved format)
  if (spec.nodes.length === 0) return false
  return true
}

export function useDiagramImport() {
  const router = useRouter()
  const { isZh } = useLanguage()
  const notify = useNotifications()

  function triggerImport(): void {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json,application/json'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      try {
        const text = await file.text()
        const parsed = JSON.parse(text) as unknown
        if (!isValidDiagramSpec(parsed)) {
          notify.error(
            isZh.value
              ? '无效的图示文件，请选择 MindGraph 导出的 JSON 文件'
              : 'Invalid diagram file. Please select a JSON file exported from MindGraph.'
          )
          return
        }
        sessionStorage.setItem(IMPORT_SPEC_KEY, text)
        router.push({ path: '/canvas', query: { import: '1' } })
      } catch (error) {
        console.error('Import failed:', error)
        notify.error(
          isZh.value ? '无法解析 JSON 文件，请重试' : 'Failed to parse JSON file, please try again'
        )
      }
    }
    input.click()
  }

  return { triggerImport }
}
