/**
 * Slot option lists and labels for worksheet dual-diagram compare mode.
 */
import { type Ref, computed, onMounted, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useSnapshotHistory } from '@/composables/editor/useSnapshotHistory'
import { CANVAS_LLM_MENU, canvasMenuModelDisplayName } from '@/config/canvasLlmMenu'
import { type WorksheetCompareSlot, worksheetCompareSlotKey } from '@/config/canvasWorksheetText'
import { useSavedDiagramsStore } from '@/stores'
import { useLLMResultsStore } from '@/stores/llmResults'

export type WorksheetCompareSourceOption = {
  value: string
  label: string
  labelKey?: string
  labelParams?: Record<string, string>
  disabled?: boolean
}

export function useWorksheetCompareSources(enabled: Ref<boolean>) {
  const { t } = useLanguage()
  const llmResults = useLLMResultsStore()
  const savedDiagrams = useSavedDiagramsStore()
  const { snapshots, loadSnapshots } = useSnapshotHistory()

  async function refreshSnapshots(): Promise<void> {
    const diagramId = savedDiagrams.activeDiagramId
    if (!diagramId) return
    await loadSnapshots(diagramId)
  }

  onMounted(() => {
    if (enabled.value) void refreshSnapshots()
  })

  watch(enabled, (on) => {
    if (on) void refreshSnapshots()
  })

  watch(
    () => savedDiagrams.activeDiagramId,
    () => {
      if (enabled.value) void refreshSnapshots()
    }
  )

  const modelOptions = computed(() => {
    return llmResults.readyModels.map((modelId) => {
      const menu = CANVAS_LLM_MENU.find((item) => item.id === modelId)
      const fallback = menu ? t(menu.labelKey) : modelId
      return {
        value: worksheetCompareSlotKey({ kind: 'model', id: modelId }),
        label: canvasMenuModelDisplayName(fallback),
      }
    })
  })

  const snapshotOptions = computed(() => {
    return snapshots.value.map((snap) => {
      const when = snap.created_at
        ? new Date(snap.created_at).toLocaleString()
        : `#${snap.version_number}`
      return {
        value: worksheetCompareSlotKey({
          kind: 'snapshot',
          id: String(snap.version_number),
        }),
        label: t('canvas.worksheetText.compareSnapshotOption', {
          n: String(snap.version_number),
          when,
        }),
        labelKey: 'canvas.worksheetText.compareSnapshotOption',
        labelParams: {
          n: String(snap.version_number),
          when,
        },
      }
    })
  })

  const sourceOptions = computed((): WorksheetCompareSourceOption[] => {
    const options: WorksheetCompareSourceOption[] = [
      {
        value: 'current',
        label: t('canvas.worksheetText.compareSourceCurrent'),
        labelKey: 'canvas.worksheetText.compareSourceCurrent',
      },
    ]
    if (modelOptions.value.length > 0) {
      options.push(...modelOptions.value)
    }
    if (snapshotOptions.value.length > 0) {
      options.push(...snapshotOptions.value)
    }
    return options
  })

  const hasModels = computed(() => modelOptions.value.length > 0)
  const hasSnapshots = computed(() => snapshotOptions.value.length > 0)

  function labelForSlot(slot: WorksheetCompareSlot): string {
    const key = worksheetCompareSlotKey(slot)
    const hit = sourceOptions.value.find((option) => option.value === key)
    return hit?.label ?? t('canvas.worksheetText.compareSourceCurrent')
  }

  return {
    sourceOptions,
    hasModels,
    hasSnapshots,
    labelForSlot,
    refreshSnapshots,
  }
}
