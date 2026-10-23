/**
 * Canvas model menu shared by the desktop status bar and the mobile canvas.
 * Express (DeepSeek mark) stays the default. A school model replaces the list.
 */
import { type ComputedRef, computed } from 'vue'

import { useCanvasDiagramTranslate } from '@/composables/canvasToolbar/useCanvasDiagramTranslate'
import { useLanguage } from '@/composables/core/useLanguage'
import { useCanvasLlmModelNames } from '@/composables/llm/useCanvasLlmModelNames'
import { useOrgCustomLlm } from '@/composables/llm/useOrgCustomLlm'
import {
  CANVAS_LLM_MENU,
  type CanvasLlmLogo,
  canvasLlmLogo,
  canvasMenuModelLabel,
} from '@/config/canvasLlmMenu'
import { useLLMResultsStore } from '@/stores'
import { selectCanvasLlmModel } from '@/stores/llmMenuChoice'

export interface CanvasLlmMenuRow {
  id: string
  label: string
  model: string
  logo: CanvasLlmLogo
}

export interface CanvasLlmMenuApi {
  llmMenu: ComputedRef<CanvasLlmMenuRow[]>
  selectedLlm: ComputedRef<string>
  selectedLlmRow: ComputedRef<CanvasLlmMenuRow | undefined>
  selectLlm: (model: string) => void
}

export function useCanvasLlmMenu(): CanvasLlmMenuApi {
  const llmResultsStore = useLLMResultsStore()
  const { leaveTranslatePreview } = useCanvasDiagramTranslate()
  const { t } = useLanguage()
  const { customLlmEnabled, displayNameForModel } = useOrgCustomLlm()
  const { names: canvasModelNames } = useCanvasLlmModelNames()

  const llmMenu = computed<CanvasLlmMenuRow[]>(() => {
    if (customLlmEnabled.value) {
      return [
        {
          id: 'qwen',
          label: displayNameForModel('qwen'),
          model: '',
          logo: canvasLlmLogo('qwen'),
        },
      ]
    }
    return CANVAS_LLM_MENU.map((item) => ({
      id: item.id,
      label: String(t(item.labelKey)),
      model: canvasMenuModelLabel(item.id, canvasModelNames.value, String(t(item.modelKey))),
      logo: item.logo,
    }))
  })

  const selectedLlm = computed(() => {
    const current = llmResultsStore.canvasModelChoice
    if (current && llmMenu.value.some((item) => item.id === current)) {
      return current
    }
    return customLlmEnabled.value ? 'qwen' : 'express'
  })

  const selectedLlmRow = computed(
    () => llmMenu.value.find((item) => item.id === selectedLlm.value) ?? llmMenu.value[0]
  )

  function selectLlm(model: string): void {
    void leaveTranslatePreview().then(() => {
      void selectCanvasLlmModel(model)
    })
  }

  return {
    llmMenu,
    selectedLlm,
    selectedLlmRow,
    selectLlm,
  }
}
