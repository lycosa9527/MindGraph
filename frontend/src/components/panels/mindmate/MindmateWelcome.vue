<script setup lang="ts">
import { computed } from 'vue'

import { ElAvatar } from 'element-plus'

import { useLanguage } from '@/composables'

import mindmateAvatarLg from '@/assets/mindmate-avatar-lg.png'
import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'

const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
  }>(),
  {
    mode: 'panel',
  }
)

const { isZh } = useLanguage()
const isFullpageMode = computed(() => props.mode === 'fullpage')
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
      <div class="text-2xl font-medium text-gray-800 mb-2">
        {{ isZh ? '你好' : 'Hello' }}
      </div>
      <div class="text-lg text-gray-600">
        {{
          isZh
            ? '我是你的虚拟教研伙伴MindMate'
            : "I'm MindMate, your virtual teaching partner"
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
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
        {{ isZh ? 'MindMate AI 已就绪' : 'MindMate AI is Ready' }}
      </h3>
      <p class="text-sm text-gray-600 dark:text-gray-300">
        {{ isZh ? '有什么可以帮助您的吗？' : 'How can I help you today?' }}
      </p>
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';
</style>
