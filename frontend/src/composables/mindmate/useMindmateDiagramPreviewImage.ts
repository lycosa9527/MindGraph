/**
 * Resolve MindMate generate_dingtalk preview images from IndexedDB or live fetch,
 * so previews survive server temp_images cleanup (24h).
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import {
  hasGeneratedDiagramImage,
  rewriteMindmateTempImageUrls,
  stripMindmateDiagramIdComments,
} from '@/utils/mindmateDiagramMeta'
import { replaceMindmatePreviewImageUrl } from '@/utils/mindmateDiagramPreviewDisplay'
import { resolveMindmateDiagramPreviewBlob } from '@/utils/mindmateDiagramPreviewResolve'

export function useMindmateDiagramPreviewImage(options: {
  content: () => string
  isStreaming: () => boolean
  pageHost?: () => string | undefined
  libraryDiagramId?: () => string | null
}) {
  const previewBlobUrl = ref<string | null>(null)
  let activeBlobUrl: string | null = null
  let resolveRequestId = 0

  function setPreviewBlob(blob: Blob): void {
    if (activeBlobUrl) {
      URL.revokeObjectURL(activeBlobUrl)
      activeBlobUrl = null
    }
    const url = URL.createObjectURL(blob)
    activeBlobUrl = url
    previewBlobUrl.value = url
  }

  function clearPreviewBlob(): void {
    if (activeBlobUrl) {
      URL.revokeObjectURL(activeBlobUrl)
      activeBlobUrl = null
    }
    previewBlobUrl.value = null
  }

  async function resolvePreview(): Promise<void> {
    if (options.isStreaming()) {
      return
    }
    const rawContent = options.content()
    if (!hasGeneratedDiagramImage(rawContent)) {
      clearPreviewBlob()
      return
    }

    const requestId = ++resolveRequestId
    const blob = await resolveMindmateDiagramPreviewBlob({
      content: rawContent,
      pageHost: options.pageHost?.(),
      libraryDiagramId: options.libraryDiagramId?.(),
    })
    if (requestId !== resolveRequestId) {
      return
    }
    if (blob) {
      setPreviewBlob(blob)
      return
    }
    clearPreviewBlob()
  }

  watch(
    () =>
      [
        options.content(),
        options.isStreaming(),
        options.pageHost?.(),
        options.libraryDiagramId?.(),
      ] as const,
    () => {
      void resolvePreview()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    resolveRequestId += 1
    clearPreviewBlob()
  })

  const displayContent = computed(() => {
    let text = rewriteMindmateTempImageUrls(
      options.content(),
      options.pageHost?.()
    )
    if (previewBlobUrl.value) {
      text = replaceMindmatePreviewImageUrl(text, previewBlobUrl.value)
    }
    return stripMindmateDiagramIdComments(text)
  })

  return { displayContent, previewBlobUrl }
}
