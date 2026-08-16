import { computed } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  isMindMapBranchNumberingEnabled,
  mindMapBranchNumberMapFromData,
} from '@/utils/mindMapBranchNumbering'

/** Shared computed number map for v2 branch chrome and the outline sidebar. */
export function useMindMapBranchNumbering() {
  const diagramStore = useDiagramSession()

  const numberMap = computed(() => {
    const data = diagramStore.data
    void data?._mindmap_branch_numbering
    void data?._mindmap_branch_numbering_prefix
    void data?._mindmap_branch_numbering_nested
    return mindMapBranchNumberMapFromData(data)
  })

  const numberingEnabled = computed(() => isMindMapBranchNumberingEnabled(diagramStore.data))

  function prefixFor(nodeId: string): string {
    return numberMap.value.get(nodeId) ?? ''
  }

  return {
    numberMap,
    numberingEnabled,
    prefixFor,
  }
}
