/**
 * One personal-knowledge folder for the diagram on the canvas.
 * A new diagram starts with none. The settings store is not read.
 */
import { computed, shallowRef, watch } from 'vue'

import { usePackages } from '@/composables/fileCenter/useFileCenter'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { apiRequestJson } from '@/utils/apiClient'
import { knowledgeButtonOn, nextKnowledgeFolderId } from '@/utils/diagramKnowledgeSelection'
import { folderIsReady } from '@/utils/knowledgeWorkTone'

const selectedPackageId = shallowRef<number | null>(null)
const generatePackageId = shallowRef<number | null>(null)
let watchStarted = false

export function currentPersonalKnowledgePackageId(): number | null {
  return generatePackageId.value
}

async function persistPackage(diagramId: string, packageId: number | null): Promise<boolean> {
  try {
    await apiRequestJson(`/api/diagrams/${diagramId}/knowledge-package`, {
      method: 'PUT',
      body: JSON.stringify({ package_id: packageId }),
    })
    const store = useSavedDiagramsStore()
    await store.getDiagram(diagramId, { force: true })
    return true
  } catch {
    return false
  }
}

function startDiagramWatch(): void {
  if (watchStarted) return
  watchStarted = true
  const store = useSavedDiagramsStore()
  let loadToken = 0
  watch(
    () => store.activeDiagramId,
    (diagramId, previousId) => {
      const token = ++loadToken
      if (diagramId === null) {
        selectedPackageId.value = null
        return
      }
      if (previousId === null && selectedPackageId.value !== null) {
        void persistPackage(diagramId, selectedPackageId.value)
        return
      }
      void store.getDiagram(diagramId, { force: true }).then((result) => {
        if (token !== loadToken) return
        selectedPackageId.value = result.ok ? (result.diagram.knowledge_package_id ?? null) : null
      })
    },
    { immediate: true }
  )
}

export function useDiagramKnowledgeSelection() {
  startDiagramWatch()
  const packagesQuery = usePackages()
  const buttonOn = computed(() => {
    const packageId = selectedPackageId.value
    if (packageId === null) return false
    const folder = (packagesQuery.data.value?.packages ?? []).find((item) => item.id === packageId)
    return knowledgeButtonOn(packageId, folder ? folderIsReady(folder) : false)
  })
  const packageIdForGenerate = computed(() => (buttonOn.value ? selectedPackageId.value : null))
  watch(
    packageIdForGenerate,
    (packageId) => {
      generatePackageId.value = packageId
    },
    { immediate: true }
  )

  function chooseFolder(folderId: number, ready: boolean): void {
    const next = nextKnowledgeFolderId(selectedPackageId.value, folderId, ready)
    if (next === selectedPackageId.value) return
    const previous = selectedPackageId.value
    selectedPackageId.value = next
    const diagramId = useSavedDiagramsStore().activeDiagramId
    if (!diagramId) return
    void persistPackage(diagramId, next).then((saved) => {
      if (!saved && selectedPackageId.value === next) {
        selectedPackageId.value = previous
      }
    })
  }

  return {
    selectedPackageId,
    buttonOn,
    packageIdForGenerate,
    chooseFolder,
  }
}
