import { ref } from 'vue'

import { workshopImageLightboxFromClick } from '@/utils/workshopMessageImageLightbox'

export function useWorkshopImageLightbox(fallbackFilename: () => string) {
  const lightboxSrc = ref<string | null>(null)
  const lightboxName = ref('')

  function handleMarkdownImageClick(event: Event): void {
    const hit = workshopImageLightboxFromClick(event, fallbackFilename())
    if (!hit) {
      return
    }
    lightboxSrc.value = hit.src
    lightboxName.value = hit.filename
  }

  function closeLightbox(): void {
    lightboxSrc.value = null
  }

  return {
    lightboxSrc,
    lightboxName,
    handleMarkdownImageClick,
    closeLightbox,
  }
}
