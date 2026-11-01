<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'

import { useLanguage } from '@/composables'

/** Publish form previews diagrams on the editor canvas. Load it only while open. */
const PublishShowcaseModal = defineAsyncComponent(
  () => import('@/components/showcase/PublishShowcaseModal.vue')
)

const { t } = useLanguage()
const showModal = ref(false)

const hint = computed(() => String(t('admin.showcase.proxyIntro')))
</script>

<template>
  <div class="space-y-4 rounded-xl border border-gray-200 bg-white p-6">
    <p class="text-sm text-gray-600">
      {{ hint }}
    </p>
    <button
      type="button"
      class="rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
      @click="showModal = true"
    >
      <I18nText k="admin.showcase.openProxyForm" />
    </button>
    <PublishShowcaseModal
      v-if="showModal"
      v-model:visible="showModal"
      proxy-mode
      @success="showModal = false"
    />
  </div>
</template>
