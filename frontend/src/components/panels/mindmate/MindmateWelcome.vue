<script setup lang="ts">
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import { useAuthStore } from '@/stores/auth'

import MindmateAgentAvatar from './MindmateAgentAvatar.vue'

const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
  }>(),
  {
    mode: 'panel',
  }
)

const { t } = useLanguage()
const authStore = useAuthStore()
const isFullpageMode = computed(() => props.mode === 'fullpage')
const { displayName } = useMindMateBranding('md')
const welcomeBrandingSize = computed(() => (isFullpageMode.value ? 'lg' : 'md') as 'md' | 'lg')
const welcomeAvatarSize = computed(() => (isFullpageMode.value ? 128 : 64))
const username = computed(() => authStore.user?.username || '')
const welcomeMessage = computed(() =>
  t('mindmate.welcome', { username: username.value, agentName: displayName.value })
)
</script>

<template>
  <div
    v-if="isFullpageMode"
    class="welcome-fullpage"
  >
    <MindmateAgentAvatar
      :size="welcomeAvatarSize"
      :branding-size="welcomeBrandingSize"
      avatar-class="mindmate-avatar-welcome"
    />
    <div class="text-center mt-6">
      <div class="text-2xl font-medium text-gray-800 mb-2">{{ displayName }}</div>
      <div class="text-lg text-gray-600">
        {{ welcomeMessage }}
      </div>
    </div>
  </div>

  <div
    v-else
    class="welcome-panel"
  >
    <div
      class="welcome-card bg-gradient-to-br from-primary-50 to-purple-50 dark:from-gray-700 dark:to-gray-600 rounded-xl p-6 text-center"
    >
      <MindmateAgentAvatar
        :size="64"
        branding-size="md"
        avatar-class="mindmate-avatar mx-auto mb-3"
      />
      <p class="text-sm font-medium text-gray-800 dark:text-gray-200 mb-1">
        {{ displayName }}
      </p>
      <p class="text-sm text-gray-600 dark:text-gray-300">
        {{ welcomeMessage }}
      </p>
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';
</style>
