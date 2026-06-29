/**
 * Document Summary session package — idempotent start/resume on panel open.
 */
import { type InjectionKey, type Ref, computed, inject, ref, watch } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'
import { storeToRefs } from 'pinia'

import { useSavedDiagramsStore, useDiagramStore } from '@/stores'
import { apiRequestJson } from '@/utils/apiClient'

import {
  type KnowledgePackage,
  type PackageListResponse,
  fileCenterKeys,
  useFileCenterMutations,
  usePackages,
} from './useFileCenter'

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
  const diagramStore = useDiagramStore()
  const queryClient = useQueryClient()
  const { activeDiagramId } = storeToRefs(savedDiagramsStore)
  const { updatePackage } = useFileCenterMutations()

  const packagesQuery = usePackages({ enabled })
  const pendingPackageId = ref<number | null>(readPendingPackageId())
  const sessionStarting = ref(false)
  /** Immediately updated after session/start so ingest does not wait on query refetch. */
  const sessionPackageId = ref<number | null>(null)

  const linkedPackage = computed<KnowledgePackage | null>(() => {
    const diagramId = activeDiagramId.value
    const packages = packagesQuery.data.value?.packages ?? []

    if (sessionPackageId.value !== null) {
      const sessionMatch = packages.find((pkg) => pkg.id === sessionPackageId.value)
      if (sessionMatch) {
        return sessionMatch
      }
    }

    if (diagramId) {
      const match = packages.find((pkg) => pkg.diagram_id === diagramId)
      if (match) return match
    }
    if (pendingPackageId.value !== null) {
      return packages.find((pkg) => pkg.id === pendingPackageId.value) ?? null
    }
    return null
  })

  const activePackageId = computed<number | null>(
    () => sessionPackageId.value ?? linkedPackage.value?.id ?? null
  )

  function rememberPendingPackage(packageId: number): void {
    pendingPackageId.value = packageId
    sessionPackageId.value = packageId
    writePendingPackageId(packageId)
  }

  function clearPendingPackage(): void {
    pendingPackageId.value = null
    writePendingPackageId(null)
  }

  function mergeSessionPackageIntoCache(pkg: KnowledgePackage): void {
    queryClient.setQueryData<PackageListResponse>(fileCenterKeys.packages(), (existing) => {
      const packages = existing?.packages ?? []
      const found = packages.some((item) => item.id === pkg.id)
      const wikiCompileEnabled = existing?.wiki_compile_enabled ?? false
      if (found) {
        return {
          packages: packages.map((item) => (item.id === pkg.id ? { ...item, ...pkg } : item)),
          total: existing?.total ?? packages.length,
          wiki_compile_enabled: wikiCompileEnabled,
        }
      }
      return {
        packages: [pkg, ...packages],
        total: (existing?.total ?? 0) + 1,
        wiki_compile_enabled: wikiCompileEnabled,
      }
    })
  }

  /** Link the pending package to the diagram once it receives its first persisted id. */
  async function linkPendingPackage(diagramId: string): Promise<void> {
    const pkg = linkedPackage.value
    if (!pkg || pkg.diagram_id === diagramId) {
      return
    }
    await updatePackage.mutateAsync({ packageId: pkg.id, diagram_id: diagramId })
    clearPendingPackage()
  }

  /** Resume an existing session package without creating an empty one. */
  async function resolveSession(): Promise<KnowledgePackage | null> {
    if (!enabled.value) {
      return null
    }
    sessionStarting.value = true
    try {
      const pkg = await apiRequestJson<KnowledgePackage>(
        '/api/knowledge-space/doc-summary/session/start',
        {
          method: 'POST',
          body: JSON.stringify({
            diagram_id: activeDiagramId.value ?? undefined,
            diagram_title: diagramStore.effectiveTitle || undefined,
            package_id: pendingPackageId.value ?? linkedPackage.value?.id ?? undefined,
            create_if_missing: false,
          }),
        }
      )
      sessionPackageId.value = pkg.id
      mergeSessionPackageIntoCache(pkg)
      if (!activeDiagramId.value) {
        rememberPendingPackage(pkg.id)
      }
      void queryClient.invalidateQueries({ queryKey: fileCenterKeys.packages() })
      return pkg
    } catch {
      return null
    } finally {
      sessionStarting.value = false
    }
  }

  /** Create the session package on first ingest (or chat pairing). */
  async function ensureSession(): Promise<KnowledgePackage> {
    if (!enabled.value) {
      throw new Error('Document Summary is disabled')
    }
    if (sessionStarting.value && sessionPackageId.value !== null) {
      const cached = linkedPackage.value
      if (cached) {
        return cached
      }
    }
    sessionStarting.value = true
    try {
      const pkg = await apiRequestJson<KnowledgePackage>(
        '/api/knowledge-space/doc-summary/session/start',
        {
          method: 'POST',
          body: JSON.stringify({
            diagram_id: activeDiagramId.value ?? undefined,
            diagram_title: diagramStore.effectiveTitle || undefined,
            package_id: pendingPackageId.value ?? linkedPackage.value?.id ?? undefined,
            create_if_missing: true,
          }),
        }
      )
      sessionPackageId.value = pkg.id
      mergeSessionPackageIntoCache(pkg)
      if (!activeDiagramId.value) {
        rememberPendingPackage(pkg.id)
      }
      void queryClient.invalidateQueries({ queryKey: fileCenterKeys.packages() })
      return pkg
    } finally {
      sessionStarting.value = false
    }
  }

  watch(
    () => activeDiagramId.value,
    (diagramId, previousDiagramId) => {
      if (diagramId && !previousDiagramId && pendingPackageId.value !== null) {
        void linkPendingPackage(diagramId)
      }
    }
  )

  return {
    packagesQuery,
    linkedPackage,
    activePackageId,
    activeDiagramId,
    sessionStarting,
    rememberPendingPackage,
    clearPendingPackage,
    resolveSession,
    ensureSession,
  }
}

export function useFileCenterActivePackage(enabled: Ref<boolean>) {
  const injected = inject(FILE_CENTER_ACTIVE_PACKAGE_KEY, null)
  if (injected) {
    return injected
  }
  return createFileCenterActivePackage(enabled)
}
