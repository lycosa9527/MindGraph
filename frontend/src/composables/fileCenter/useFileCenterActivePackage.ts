/**
 * Resolves the File Center package bound to the diagram currently on canvas.
 *
 * A package may be created before the diagram is first saved (unsaved-diagram
 * session): in that case we remember the pending package id in sessionStorage
 * and link it to the diagram as soon as the first save assigns a diagram id.
 */
import { type InjectionKey, type Ref, computed, inject, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { useSavedDiagramsStore } from '@/stores'

import { type KnowledgePackage, useFileCenterMutations, usePackages } from './useFileCenter'

const PENDING_PACKAGE_KEY = 'mindgraph.fileCenter.pendingPackageId'

function readPendingPackageId(): number | null {
  const raw = sessionStorage.getItem(PENDING_PACKAGE_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function writePendingPackageId(packageId: number | null): void {
  if (packageId === null) {
    sessionStorage.removeItem(PENDING_PACKAGE_KEY)
  } else {
    sessionStorage.setItem(PENDING_PACKAGE_KEY, String(packageId))
  }
}

export type FileCenterActivePackageContext = ReturnType<typeof createFileCenterActivePackage>

export const FILE_CENTER_ACTIVE_PACKAGE_KEY: InjectionKey<FileCenterActivePackageContext> =
  Symbol('fileCenterActivePackage')

export function createFileCenterActivePackage(enabled: Ref<boolean>) {
  const savedDiagramsStore = useSavedDiagramsStore()
  const { activeDiagramId } = storeToRefs(savedDiagramsStore)
  const { updatePackage } = useFileCenterMutations()

  const packagesQuery = usePackages({ enabled })
  const pendingPackageId = ref<number | null>(readPendingPackageId())

  const linkedPackage = computed<KnowledgePackage | null>(() => {
    const diagramId = activeDiagramId.value
    const packages = packagesQuery.data.value?.packages ?? []
    if (diagramId) {
      const match = packages.find((pkg) => pkg.diagram_id === diagramId)
      if (match) return match
    }
    if (pendingPackageId.value !== null) {
      return packages.find((pkg) => pkg.id === pendingPackageId.value) ?? null
    }
    return null
  })

  const activePackageId = computed<number | null>(() => linkedPackage.value?.id ?? null)

  function rememberPendingPackage(packageId: number): void {
    pendingPackageId.value = packageId
    writePendingPackageId(packageId)
  }

  function clearPendingPackage(): void {
    pendingPackageId.value = null
    writePendingPackageId(null)
  }

  /** Link the pending package to the diagram once it has a persisted id. */
  async function linkPendingPackage(diagramId: string): Promise<void> {
    const pkg = linkedPackage.value
    if (!pkg || pkg.diagram_id === diagramId) {
      return
    }
    await updatePackage.mutateAsync({ packageId: pkg.id, diagram_id: diagramId })
    clearPendingPackage()
  }

  watch(
    () => activeDiagramId.value,
    (diagramId) => {
      if (diagramId && pendingPackageId.value !== null) {
        void linkPendingPackage(diagramId)
      }
    }
  )

  return {
    packagesQuery,
    linkedPackage,
    activePackageId,
    activeDiagramId,
    rememberPendingPackage,
    clearPendingPackage,
  }
}

export function useFileCenterActivePackage(enabled: Ref<boolean>) {
  const injected = inject(FILE_CENTER_ACTIVE_PACKAGE_KEY, null)
  if (injected) {
    return injected
  }
  return createFileCenterActivePackage(enabled)
}
