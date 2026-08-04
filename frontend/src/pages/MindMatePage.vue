<script setup lang="ts">
/**
 * MindMatePage - Full-page MindMate chat interface
 * Route: /mindmate
 */
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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

interface MindmatePanelHandle {
  prefillCollabJoin: (rawCode: string) => void
  attachShowcasePost: (postId: string) => Promise<void>
}

const mindmatePanelRef = ref<MindmatePanelHandle | null>(null)

useMindmateCollabNotify()

async function consumeJoinCollabQuery(): Promise<void> {
  const joinCode = route.query.join_mindmate_collab
  if (typeof joinCode !== 'string' || !joinCode.trim()) return

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
  await nextTick()
  mindmatePanelRef.value?.prefillCollabJoin(joinCode.trim())
}

async function consumeShowcasePostQuery(): Promise<void> {
  const postId = route.query.showcase_post
  if (typeof postId !== 'string' || !postId.trim()) return

  const nextQuery = { ...route.query }
  delete nextQuery.showcase_post
  void router.replace({ query: nextQuery })

  await nextTick()
  await mindmatePanelRef.value?.attachShowcasePost(postId.trim())
}

onMounted(async () => {
  void ensureMarkdownRenderer()
  void authStore.checkAuth(true)
  await featureFlagsStore.fetchFlags()
  await consumeJoinCollabQuery()
  await consumeShowcasePostQuery()
})

watch(
  () => route.query.showcase_post,
  (value) => {
    if (typeof value === 'string' && value.trim()) {
      void consumeShowcasePostQuery()
    }
  }
)

onUnmounted(() => {
  useVoiceStore().reset()
})
</script>

<template>
  <div class="mindmate-page flex-1 flex flex-col min-h-0 min-w-0 bg-white">
    <MindmatePanel
      ref="mindmatePanelRef"
      mode="fullpage"
      class="flex-1"
    />
  </div>
</template>
