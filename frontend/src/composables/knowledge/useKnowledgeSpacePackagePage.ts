/**
 * Package-scoped Knowledge Space page state (sidebar selection + main panel).
 */
import { computed, watch } from 'vue'

import { ElMessageBox } from 'element-plus'
import { useQueryClient } from '@tanstack/vue-query'
import { storeToRefs } from 'pinia'

import { notify, useLanguage } from '@/composables'
import {
  fileCenterKeys,
  useFileCenterMutations,
  usePackageDetail,
  usePackages,
} from '@/composables/fileCenter/useFileCenter'
import { useProcessSelected } from '@/composables/queries'
import { useKnowledgeSpaceStore } from '@/stores/knowledgeSpace'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { MAX_KNOWLEDGE_PACKAGES } from '@/utils/knowledgePackageLimit'

const MAX_SOURCES_PER_PACKAGE = 5

export function useKnowledgeSpacePackagePage() {
  const { t } = useLanguage()
  const queryClient = useQueryClient()
  const store = useKnowledgeSpaceStore()
  const { activePackageId } = storeToRefs(store)

  const packagesQuery = usePackages()
  const packages = computed(() => packagesQuery.data.value?.packages ?? [])

  const detailQuery = usePackageDetail(activePackageId)
  const activePackage = computed(() => detailQuery.data.value?.package ?? null)
  const documents = computed(() => detailQuery.data.value?.documents ?? [])

  const loading = computed(() => packagesQuery.isLoading.value || detailQuery.isLoading.value)
  const uploading = computed(() => uploadFile.isPending.value)

  const documentCount = computed(() => documents.value.length)
  const completedCount = computed(
    () => documents.value.filter((doc: KnowledgeDocument) => doc.status === 'completed').length
  )
  const pendingCount = computed(
    () =>
      documents.value.filter(
        (doc: KnowledgeDocument) => doc.status === 'pending' || doc.status === 'failed'
      ).length
  )
  const canUpload = computed(
    () => activePackageId.value !== null && documentCount.value < MAX_SOURCES_PER_PACKAGE
  )

  const activePackageName = computed(() => {
    if (!activePackage.value) return null
    return activePackage.value.name?.trim() || t('fileCenter.defaultPackageName')
  })

  const packageCountLabel = computed(() => `${packages.value.length}/${MAX_KNOWLEDGE_PACKAGES}`)

  const { uploadFile, deleteSource, startProcessing } = useFileCenterMutations()
  const processSelectedMutation = useProcessSelected()

  watch(
    packages,
    (items) => {
      if (activePackageId.value === null) return
      const stillExists = items.some((pkg) => pkg.id === activePackageId.value)
      if (!stillExists) {
        store.selectPackage(null)
      }
    },
    { immediate: true }
  )

  async function uploadDocument(file: File): Promise<void> {
    const packageId = activePackageId.value
    if (packageId === null || !canUpload.value) return
    await uploadFile.mutateAsync({ packageId, file })
    notify.success(t('knowledgeSpace.uploadSuccessProcessing'))
  }

  async function deleteDocument(documentId: number): Promise<void> {
    const packageId = activePackageId.value
    if (packageId === null) return
    try {
      await ElMessageBox.confirm(
        t('knowledgeSpace.confirmDeleteBody'),
        t('knowledgeSpace.confirmDeleteTitle'),
        {
          confirmButtonText: t('common.delete'),
          cancelButtonText: t('common.cancel'),
          type: 'warning',
        }
      )
      await deleteSource.mutateAsync({ packageId, documentId })
      notify.success(t('knowledgeSpace.documentDeleted'))
    } catch (error) {
      if (error !== 'cancel') {
        notify.error(t('knowledgeSpace.deleteFailed'))
      }
    }
  }

  async function startPackageProcessing(): Promise<void> {
    const packageId = activePackageId.value
    if (packageId === null) return
    try {
      const result = await startProcessing.mutateAsync(packageId)
      if (result.processed_count === 0) {
        notify.info(t('knowledgeSpace.noPendingDocs'))
      } else {
        notify.success(t('knowledgeSpace.processingStarted', { count: result.processed_count }))
      }
    } catch {
      notify.error(t('knowledgeSpace.startProcessingFailed'))
    }
  }

  function processSelected(documentIds: number[]): void {
    if (documentIds.length === 0) return
    processSelectedMutation.mutate(documentIds, {
      onSuccess: () => {
        const packageId = activePackageId.value
        if (packageId !== null) {
          void queryClient.invalidateQueries({ queryKey: fileCenterKeys.package(packageId) })
        }
      },
    })
  }

  function resumePolling(): void {
    if (activePackageId.value !== null) {
      void detailQuery.refetch()
    }
  }

  return {
    activePackageId,
    activePackage,
    activePackageName,
    packages,
    packagesQuery,
    detailQuery,
    documents,
    loading,
    uploading,
    documentCount,
    completedCount,
    pendingCount,
    canUpload,
    packageCountLabel,
    selectPackage: store.selectPackage,
    uploadDocument,
    deleteDocument,
    startProcessing: startPackageProcessing,
    processSelected,
    resumePolling,
  }
}
