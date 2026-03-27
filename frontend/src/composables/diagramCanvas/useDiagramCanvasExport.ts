import { type Ref, ref } from 'vue'

import {
  getDefaultDiagramName,
  useDiagramExport,
  useDiagramSpecForSave,
  useLanguage,
} from '@/composables'
import { useDiagramStore } from '@/stores'

export interface UseDiagramCanvasExportOptions {
  vueFlowWrapper: Ref<HTMLElement | null>
  diagramStore: ReturnType<typeof useDiagramStore>
}

export function useDiagramCanvasExport(options: UseDiagramCanvasExportOptions) {
  const { vueFlowWrapper, diagramStore } = options

  const { currentLanguage } = useLanguage()

  const showExportToCommunityModal = ref(false)

  function getExportContainer(): HTMLElement | null {
    return vueFlowWrapper.value
  }

  function getExportTitle(): string {
    const topicText = diagramStore.getTopicNodeText()
    if (topicText) return topicText
    return (
      diagramStore.effectiveTitle || getDefaultDiagramName(diagramStore.type, currentLanguage.value)
    )
  }

  const getExportSpec = useDiagramSpecForSave()

  const { exportByFormat } = useDiagramExport({
    getContainer: () => vueFlowWrapper.value,
    getDiagramSpec: getExportSpec,
    getTitle: getExportTitle,
  })

  return {
    showExportToCommunityModal,
    getExportContainer,
    getExportTitle,
    getExportSpec,
    exportByFormat,
  }
}
