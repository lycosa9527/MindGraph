<script setup lang="ts">
/**
 * Keeps the 研习社 chat WebSocket alive for the whole desktop app so
 * toasts and sidebar unread update while the user is on MindMate / canvas.
 */
import { watch } from 'vue'

import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useWorkshopChatComposable } from '@/composables/workshop/useWorkshopChat'
import { useAuthStore } from '@/stores/auth'
import { userCanAccessWorkshopChat } from '@/utils/workshopAccess'

const ws = useWorkshopChatComposable()
const authStore = useAuthStore()
const { featureWorkshopChat, workshopChatPreviewOrgIds, featureOrgAccess } = useFeatureFlags()

function canConnect(): boolean {
  if (!authStore.isAuthenticated || !featureWorkshopChat.value) {
    return false
  }
  return userCanAccessWorkshopChat(
    authStore.isAdmin,
    authStore.user?.schoolId,
    authStore.user?.id,
    workshopChatPreviewOrgIds.value,
    featureOrgAccess.value.feature_workshop_chat
  )
}

watch(
  () => [
    authStore.isAuthenticated,
    featureWorkshopChat.value,
    authStore.user?.id,
    authStore.user?.schoolId,
    workshopChatPreviewOrgIds.value,
    featureOrgAccess.value.feature_workshop_chat,
  ],
  () => {
    if (canConnect()) {
      ws.connect()
      return
    }
    ws.disconnect()
  },
  { immediate: true }
)
</script>

<template></template>
