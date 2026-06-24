/**
 * File Center (文件中心) — Zotero-like knowledge packages for diagram RAG.
 *
 * A package is a named collection of sources (PDF, DOCX, pasted text, web
 * snapshots) scoped to one diagram. Sources are chunked and indexed exactly
 * like ordinary Knowledge Space documents; the completed sources scope RAG
 * retrieval when the diagram is completed by the LLM.
 *
 * This composable wraps the `/api/knowledge-space/packages` endpoints with
 * Vue Query and exposes a small facade for the File Center panel.
 */
import { type MaybeRef, computed, unref } from 'vue'

import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { apiRequestJson, apiUpload } from '@/utils/apiClient'

// ============================================================================
// Types
// ============================================================================

export type PackageSource = 'canvas' | 'knowledge_space' | 'chrome_extension'

export interface KnowledgePackage {
  id: number
  name: string | null
  diagram_id: string | null
  source: string | null
  status: string
  document_count: number
  completed_count: number
  created_at: string
  updated_at: string
}

export interface PackageListResponse {
  packages: KnowledgePackage[]
  total: number
}

export interface PackageDetailResponse {
  package: KnowledgePackage
  documents: KnowledgeDocument[]
}

export interface CreatePackagePayload {
  name: string
  diagram_id?: string | null
  source?: PackageSource
}

export interface IngestTextPayload {
  content: string
  title?: string
  language?: string
}

export interface IngestWebPayload {
  page_content: string
  page_url?: string
  page_title?: string
  language?: string
}

// ============================================================================
// Query keys
// ============================================================================

export const fileCenterKeys = {
  all: ['file-center'] as const,
  packages: () => [...fileCenterKeys.all, 'packages'] as const,
  package: (packageId: number) => [...fileCenterKeys.all, 'package', packageId] as const,
}

const PACKAGES_BASE = '/api/knowledge-space/packages'

/** A processing source keeps the detail query polling until everything settles. */
function hasProcessingDocuments(documents: KnowledgeDocument[]): boolean {
  return documents.some((doc) => doc.status === 'pending' || doc.status === 'processing')
}

// ============================================================================
// Queries
// ============================================================================

export function usePackages(options?: { enabled?: MaybeRef<boolean> }) {
  return useQuery({
    queryKey: fileCenterKeys.packages(),
    queryFn: () => apiRequestJson<PackageListResponse>(PACKAGES_BASE),
    staleTime: 30 * 1000,
    enabled: options?.enabled,
    retry: 1,
  })
}

export function usePackageDetail(
  packageId: MaybeRef<number | null>,
  options?: { enabled?: MaybeRef<boolean> }
) {
  return useQuery({
    queryKey: computed(() => fileCenterKeys.package(unref(packageId) ?? 0)),
    queryFn: () => {
      const id = unref(packageId)
      if (id === null) {
        throw new Error('Package id is required')
      }
      return apiRequestJson<PackageDetailResponse>(`${PACKAGES_BASE}/${id}`)
    },
    enabled: computed(() => unref(options?.enabled) !== false && unref(packageId) !== null),
    staleTime: 5 * 1000,
    // Poll while any source is still indexing so the UI reflects progress.
    refetchInterval: (query) => {
      const data = query.state.data as PackageDetailResponse | undefined
      return data && hasProcessingDocuments(data.documents) ? 4000 : false
    },
  })
}

// ============================================================================
// Mutations
// ============================================================================

export function useFileCenterMutations() {
  const queryClient = useQueryClient()
  const { t } = useLanguage()

  function invalidatePackages(): void {
    void queryClient.invalidateQueries({ queryKey: fileCenterKeys.packages() })
  }

  function invalidatePackage(packageId: number): void {
    void queryClient.invalidateQueries({ queryKey: fileCenterKeys.package(packageId) })
    invalidatePackages()
  }

  const createPackage = useMutation({
    mutationFn: (payload: CreatePackagePayload) =>
      apiRequestJson<KnowledgePackage>(PACKAGES_BASE, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidatePackages(),
    onError: (error: Error) => notify.error(error.message || t('fileCenter.createFailed')),
  })

  const updatePackage = useMutation({
    mutationFn: (vars: { packageId: number; name?: string; diagram_id?: string }) =>
      apiRequestJson<KnowledgePackage>(`${PACKAGES_BASE}/${vars.packageId}`, {
        method: 'PUT',
        body: JSON.stringify({ name: vars.name, diagram_id: vars.diagram_id }),
      }),
    onSuccess: (_data, vars) => invalidatePackage(vars.packageId),
    onError: (error: Error) => notify.error(error.message || t('fileCenter.updateFailed')),
  })

  const deletePackage = useMutation({
    mutationFn: (packageId: number) =>
      apiRequestJson<{ message: string }>(`${PACKAGES_BASE}/${packageId}`, { method: 'DELETE' }),
    onSuccess: () => invalidatePackages(),
    onError: (error: Error) => notify.error(error.message || t('fileCenter.deleteFailed')),
  })

  const uploadFile = useMutation({
    mutationFn: async (vars: { packageId: number; file: File }) => {
      const formData = new FormData()
      formData.append('file', vars.file)
      const response = await apiUpload(
        `${PACKAGES_BASE}/${vars.packageId}/documents/upload`,
        formData
      )
      if (!response.ok) {
        const error = await response.json().catch(() => null)
        throw new Error(error?.detail || t('fileCenter.uploadFailed'))
      }
      return (await response.json()) as KnowledgeDocument
    },
    onSuccess: (_data, vars) => invalidatePackage(vars.packageId),
    onError: (error: Error) => notify.error(error.message || t('fileCenter.uploadFailed')),
  })

  const ingestText = useMutation({
    mutationFn: (vars: { packageId: number; payload: IngestTextPayload }) =>
      apiRequestJson<KnowledgeDocument>(
        `${PACKAGES_BASE}/${vars.packageId}/documents/ingest-text`,
        { method: 'POST', body: JSON.stringify(vars.payload) }
      ),
    onSuccess: (_data, vars) => invalidatePackage(vars.packageId),
    onError: (error: Error) => notify.error(error.message || t('fileCenter.ingestFailed')),
  })

  const ingestWeb = useMutation({
    mutationFn: (vars: { packageId: number; payload: IngestWebPayload }) =>
      apiRequestJson<KnowledgeDocument>(`${PACKAGES_BASE}/${vars.packageId}/documents/ingest-web`, {
        method: 'POST',
        body: JSON.stringify(vars.payload),
      }),
    onSuccess: (_data, vars) => invalidatePackage(vars.packageId),
    onError: (error: Error) => notify.error(error.message || t('fileCenter.ingestFailed')),
  })

  const deleteSource = useMutation({
    mutationFn: (vars: { packageId: number; documentId: number }) =>
      apiRequestJson<{ message?: string }>(`/api/knowledge-space/documents/${vars.documentId}`, {
        method: 'DELETE',
      }),
    onSuccess: (_data, vars) => invalidatePackage(vars.packageId),
    onError: (error: Error) => notify.error(error.message || t('fileCenter.deleteFailed')),
  })

  return {
    createPackage,
    updatePackage,
    deletePackage,
    uploadFile,
    ingestText,
    ingestWeb,
    deleteSource,
  }
}
