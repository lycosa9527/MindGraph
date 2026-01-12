<script setup lang="ts">
import { computed } from 'vue'

import { ElAvatar } from 'element-plus'

import mindmateAvatarLg from '@/assets/mindmate-avatar-lg.png'
import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores/auth'

const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
  }>(),
  {
    mode: 'panel',
  }
)

const { isZh } = useLanguage()
const authStore = useAuthStore()
const isFullpageMode = computed(() => props.mode === 'fullpage')
const username = computed(() => authStore.user?.username || '')
</script>

<template>
  <!-- Welcome Message - Fullpage Mode -->
  <div
    v-if="isFullpageMode"
    class="welcome-fullpage"
  >
    <ElAvatar
      :src="mindmateAvatarLg"
      alt="MindMate"
      :size="128"
      class="mindmate-avatar-welcome"
    />
    <div class="text-center mt-6">
      <div class="text-2xl font-medium text-gray-800 mb-2">MindMate</div>
      <div class="text-lg text-gray-600">
        {{
          isZh
            ? `${username}你好，我是你的虚拟教研伙伴`
            : `Hello ${username}, I'm your virtual teaching partner`
        }}
      </div>
    </div>
  </div>

  <!-- Welcome Message - Panel Mode -->
  <div
    v-else
    class="welcome-panel"
  >
    <div
      class="welcome-card bg-gradient-to-br from-primary-50 to-purple-50 dark:from-gray-700 dark:to-gray-600 rounded-xl p-6 text-center"
    >
      <ElAvatar
        :src="mindmateAvatarMd"
        alt="MindMate"
        :size="64"
        class="mindmate-avatar mx-auto mb-3"
      />
      <p class="text-sm text-gray-600 dark:text-gray-300">
        {{
          isZh
            ? `${username}你好，我是你的虚拟教研伙伴`
            : `Hello ${username}, I'm your virtual teaching partner`
        }}
      </p>
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';
</style>
