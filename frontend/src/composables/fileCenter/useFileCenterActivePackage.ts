/**
 * Document Summary session package — idempotent start/resume on panel open.
 *
 * Session binding always follows the active diagram so ingest/generate/reset
 * stay synced with that diagram's COS extract.
 */
import { type InjectionKey, type Ref, computed, inject, ref, watch } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'
import { storeToRefs } from 'pinia'

import { DOC_SUMMARY_API_BASE } from '@/config/docSummaryApi'
import { DOC_SUMMARY_LITE_UI } from '@/config/docSummaryLite'
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
  const { updatePackage } = useFileCenterMutations({
    apiMode: DOC_SUMMARY_LITE_UI ? 'doc_summary' : 'knowledge_space',
  })

  const packagesQuery = usePackages({
    enabled: computed(() => enabled.value && !DOC_SUMMARY_LITE_UI),
    apiMode: DOC_SUMMARY_LITE_UI ? 'doc_summary' : 'knowledge_space',
  })
  const pendingPackageId = ref<number | null>(readPendingPackageId())
  const sessionStarting = ref(false)
  /** Immediately updated after session/start so ingest does not wait on query refetch. */
  const sessionPackageId = ref<number | null>(null)
  const sessionPackage = ref<KnowledgePackage | null>(null)

  const linkedPackage = computed<KnowledgePackage | null>(() => {
    if (sessionPackage.value !== null && sessionPackageId.value === sessionPackage.value.id) {
      const boundDiagramId = sessionPackage.value.diagram_id
      const activeId = activeDiagramId.value
      if (!activeId || !boundDiagramId || boundDiagramId === activeId) {
        return sessionPackage.value
      }
    }

    const diagramId = activeDiagramId.value
    const packages = packagesQuery.data.value?.packages ?? []

    if (diagramId) {
      const match = packages.find((pkg) => pkg.diagram_id === diagramId)
      if (match) return match
    }

    if (sessionPackageId.value !== null) {
      const sessionMatch = packages.find((pkg) => pkg.id === sessionPackageId.value)
      if (sessionMatch) {
        if (
          !diagramId ||
          !sessionMatch.diagram_id ||
          sessionMatch.diagram_id === diagramId
        ) {
          return sessionMatch
        }
      }
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

  /**
   * Drop in-memory session binding only (e.g. leave canvas).
   * Keeps the server package + COS extract so the diagram can resume later.
   */
  function clearLocalSession(): void {
    sessionPackageId.value = null
    sessionPackage.value = null
    sessionStarting.value = false
    clearPendingPackage()
  }

  /** Package id safe to send with the active diagram (never a cross-diagram stale id). */
  function requestPackageId(): number | undefined {
    const diagramId = activeDiagramId.value
    const candidate =
      pendingPackageId.value ?? sessionPackageId.value ?? linkedPackage.value?.id ?? null
    if (candidate === null) {
      return undefined
    }
    let pkg: KnowledgePackage | null = null
    if (sessionPackage.value?.id === candidate) {
      pkg = sessionPackage.value
    } else if (linkedPackage.value?.id === candidate) {
      pkg = linkedPackage.value
    }
    if (diagramId && pkg?.diagram_id && pkg.diagram_id !== diagramId) {
      return undefined
    }
    return candidate
  }

  async function postSessionClear(payload: {
    package_id?: number
    diagram_id?: string
  }): Promise<void> {
    await apiRequestJson<{ deleted: boolean }>(`${DOC_SUMMARY_API_BASE}/session/clear`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  /**
   * Canvas diagram reset: clear local binding and delete the Document Summary
   * package (COS markdown + Redis progress + DB rows).
   */
  function discardSession(options?: { diagramId?: string | null }): void {
    const packageId = sessionPackageId.value ?? sessionPackage.value?.id ?? null
    const diagramId = options?.diagramId ?? activeDiagramId.value ?? null
    clearLocalSession()

    if (packageId === null && !diagramId) {
      return
    }

    const payload = {
      package_id: packageId ?? undefined,
      diagram_id: diagramId ?? undefined,
    }
    void postSessionClear(payload)
      .catch(() => postSessionClear(payload))
      .catch(() => undefined)
      .finally(() => {
        void queryClient.invalidateQueries({ queryKey: fileCenterKeys.packages() })
      })
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

  function applyResolvedPackage(pkg: KnowledgePackage): void {
    sessionPackageId.value = pkg.id
    sessionPackage.value = pkg
    mergeSessionPackageIntoCache(pkg)
    if (!activeDiagramId.value) {
      rememberPendingPackage(pkg.id)
    } else {
      clearPendingPackage()
    }
    void queryClient.invalidateQueries({ queryKey: fileCenterKeys.packages() })
  }

  /** Resume an existing session package without creating an empty one. */
  async function resolveSession(): Promise<KnowledgePackage | null> {
    if (!enabled.value) {
      return null
    }
    sessionStarting.value = true
    try {
      const pkg = await apiRequestJson<KnowledgePackage>(`${DOC_SUMMARY_API_BASE}/session/start`, {
        method: 'POST',
        body: JSON.stringify({
          diagram_id: activeDiagramId.value ?? undefined,
          diagram_title: diagramStore.effectiveTitle || undefined,
          package_id: requestPackageId(),
          create_if_missing: false,
        }),
      })
      applyResolvedPackage(pkg)
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
    const diagramId = activeDiagramId.value
    if (
      sessionStarting.value &&
      sessionPackageId.value !== null &&
      (!diagramId ||
        !sessionPackage.value?.diagram_id ||
        sessionPackage.value.diagram_id === diagramId)
    ) {
      const cached = linkedPackage.value
      if (cached) {
        return cached
      }
    }
    sessionStarting.value = true
    try {
      const pkg = await apiRequestJson<KnowledgePackage>(`${DOC_SUMMARY_API_BASE}/session/start`, {
        method: 'POST',
        body: JSON.stringify({
          diagram_id: diagramId ?? undefined,
          diagram_title: diagramStore.effectiveTitle || undefined,
          package_id: requestPackageId(),
          create_if_missing: true,
        }),
      })
      applyResolvedPackage(pkg)
      return pkg
    } finally {
      sessionStarting.value = false
    }
  }

  watch(
    () => activeDiagramId.value,
    (diagramId, previousDiagramId) => {
      // Library / SPA switch: drop sticky package and rebind to the new diagram's COS.
      if (diagramId && previousDiagramId && diagramId !== previousDiagramId) {
        clearLocalSession()
        if (enabled.value) {
          void resolveSession()
        }
        return
      }
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
    clearLocalSession,
    discardSession,
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
