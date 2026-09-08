import { onMounted, onUnmounted, ref, watch, type CSSProperties, type Ref } from 'vue'

import { readTrainingPadViewport, trainingPadBox } from './trainingPadAnchor'

export function useTrainingPadAnchor(railOpen: Ref<boolean>): { padStyle: Ref<CSSProperties> } {
  const padStyle = ref<CSSProperties>({})

  function sync(): void {
    if (typeof window === 'undefined') return
    const box = trainingPadBox(readTrainingPadViewport(railOpen.value))
    padStyle.value = {
      right: `${box.right}px`,
      bottom: `${box.bottom}px`,
      maxHeight: `${box.maxHeight}px`,
    }
  }

  onMounted(() => {
    sync()
    window.visualViewport?.addEventListener('resize', sync)
    window.visualViewport?.addEventListener('scroll', sync)
    window.addEventListener('resize', sync)
  })

  onUnmounted(() => {
    window.visualViewport?.removeEventListener('resize', sync)
    window.visualViewport?.removeEventListener('scroll', sync)
    window.removeEventListener('resize', sync)
  })

  watch(railOpen, sync)

  return { padStyle }
}
