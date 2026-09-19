/**
 * Teacher assignment instruction images: local preview + COS upload refs.
 */
import { onUnmounted, ref, type Ref } from 'vue'

import { uploadInstructionImage } from '@/utils/learningSpaceApi'

export const LS_MAX_INSTRUCTION_IMAGES = 6
export const LS_MAX_INSTRUCTION_IMAGE_BYTES = 2 * 1024 * 1024

export function useLsInstructionImages(previews: Ref<string[]>) {
  const files = ref<File[]>([])

  function revokePreviews(): void {
    for (const url of previews.value) {
      if (url.startsWith('blob:')) URL.revokeObjectURL(url)
    }
  }

  function clearImages(): void {
    revokePreviews()
    previews.value = []
    files.value = []
  }

  function addImageFiles(incoming: File[]): { added: number; skipped: boolean; tooLarge: boolean } {
    const remaining = LS_MAX_INSTRUCTION_IMAGES - files.value.length
    let added = 0
    let skipped = incoming.length > remaining
    let tooLarge = false
    for (const file of incoming) {
      if (added >= remaining) {
        skipped = true
        break
      }
      if (!file.type.startsWith('image/')) continue
      if (file.size > LS_MAX_INSTRUCTION_IMAGE_BYTES) {
        tooLarge = true
        continue
      }
      files.value.push(file)
      previews.value.push(URL.createObjectURL(file))
      added += 1
    }
    return { added, skipped, tooLarge }
  }

  function removeImage(idx: number): void {
    const url = previews.value[idx]
    if (url?.startsWith('blob:')) URL.revokeObjectURL(url)
    previews.value.splice(idx, 1)
    files.value.splice(idx, 1)
  }

  async function uploadAll(classId?: number): Promise<string[]> {
    const refs: string[] = []
    for (const file of files.value) {
      const uploaded = await uploadInstructionImage(file, classId)
      refs.push(uploaded.ref)
    }
    return refs
  }

  onUnmounted(() => {
    revokePreviews()
  })

  return {
    files,
    clearImages,
    addImageFiles,
    removeImage,
    uploadAll,
  }
}
