<script setup lang="ts">
/**
 * MindMatePage - Full-page MindMate chat interface
 * Route: /mindmate
 */
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { MindmatePanel } from '@/components/panels'
import { ensureMarkdownRenderer } from '@/composables/core/useMarkdown'
import { useLanguage, useNotifications } from '@/composables'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import { useMindmateCollabNotify } from '@/composables/social/useMindmateCollabNotify'
import { useAuthStore, useVoiceStore } from '@/stores'
import { useFeatureFlagsStore } from '@/stores/featureFlags'

const authStore = useAuthStore()
const featureFlagsStore = useFeatureFlagsStore()
const { canUseOnlineCollab } = useSchoolTierFeatures()
const notify = useNotifications()
const { t } = useLanguage()
const route = useRoute()
const router = useRouter()
const mindmatePanelRef = ref<InstanceType<typeof MindmatePanel> | null>(null)

useMindmateCollabNotify()

onMounted(async () => {
  void ensureMarkdownRenderer()
  void authStore.checkAuth(true)
  await featureFlagsStore.fetchFlags()

  const joinCode = route.query.join_mindmate_collab
  if (typeof joinCode === 'string' && joinCode.trim()) {
    const nextQuery = { ...route.query }
    delete nextQuery.join_mindmate_collab
    void router.replace({ query: nextQuery })
    if (!featureFlagsStore.getFeatureMindmateCollab()) {
      return
    }
    if (!canUseOnlineCollab.value) {
      notify.warning(t('auth.schoolTierFeatureUnavailable'))
      return
    }
    mindmatePanelRef.value?.prefillCollabJoin(joinCode.trim())
  }
})

onUnmounted(() => {
  useVoiceStore().reset()
})
</script>

<template>
  <div class="mindmate-page flex-1 flex flex-col bg-white">
    <MindmatePanel
      ref="mindmatePanelRef"
      mode="fullpage"
      class="flex-1"
    />
  </div>
</template>
