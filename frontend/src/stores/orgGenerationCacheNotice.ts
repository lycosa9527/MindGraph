/**
 * Canvas notice when generate_graph served an organization-cached spec.
 * The next generate from this session sends skip_cache so the teacher gets a
 * fresh spec. That refresh is not written back to the org cache.
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

export const useOrgGenerationCacheNoticeStore = defineStore('orgGenerationCacheNotice', () => {
  const visible = ref(false)

  function show(): void {
    visible.value = true
  }

  function hide(): void {
    visible.value = false
  }

  function applyCachedFlag(cached: unknown): void {
    if (cached === true) {
      show()
      return
    }
    if (cached === false) {
      hide()
    }
  }

  return { visible, show, hide, applyCachedFlag }
})
