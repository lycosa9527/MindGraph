<script setup lang="ts">
/**
 * Bottom-right grey hint when the canvas spec came from the org cache.
 */
import { storeToRefs } from 'pinia'

import { useLanguage } from '@/composables/core/useLanguage'
import { useOrgGenerationCacheNoticeStore } from '@/stores/orgGenerationCacheNotice'

const { t } = useLanguage()
const noticeStore = useOrgGenerationCacheNoticeStore()
const { visible } = storeToRefs(noticeStore)
</script>

<template>
  <p
    v-if="visible"
    class="canvas-cached-result-notice pointer-events-none absolute bottom-3 right-3 z-10 max-w-[14rem] text-right text-[11px] leading-snug text-gray-400 dark:text-gray-500"
    role="status"
  >
    {{ t('canvas.cachedResult.notice') }}
  </p>
</template>
