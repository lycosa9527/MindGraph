<script setup lang="ts">
import { computed } from 'vue'

import { ElAvatar, ElButton, ElIcon, ElTooltip } from 'element-plus'

import { Close, Menu, Plus } from '@element-plus/icons-vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage } from '@/composables'

const props = withDefaults(
  defineProps<{
    mode?: 'panel' | 'fullpage'
    title?: string
    isTyping?: boolean
    isAuthenticated?: boolean
  }>(),
  {
    mode: 'panel',
    title: 'MindMate',
    isTyping: false,
    isAuthenticated: true,
  }
)

const emit = defineEmits<{
  (e: 'toggleHistory'): void
  (e: 'newConversation'): void
  (e: 'close'): void
}>()

const { isZh } = useLanguage()
const isFullpageMode = computed(() => props.mode === 'fullpage')
</script>

<template>
  <div
    class="panel-header h-14 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shrink-0"
  >
    <div class="flex items-center gap-2 min-w-0 flex-1">
      <!-- History button only in panel mode -->
      <ElTooltip
        v-if="!isFullpageMode"
        :content="isZh ? '历史会话' : 'Conversation History'"
      >
        <ElButton
          text
          circle
          size="small"
          class="shrink-0"
          @click="emit('toggleHistory')"
        >
          <ElIcon><Menu /></ElIcon>
        </ElButton>
      </ElTooltip>
      <!-- MindMate avatar for panel mode header -->
      <ElAvatar
        v-if="!isFullpageMode"
        :src="mindmateAvatarMd"
        alt="MindMate"
        :size="40"
        class="mindmate-avatar shrink-0"
      />
      <h1
        class="text-sm font-semibold text-gray-800 dark:text-white truncate"
        :class="{ 'typing-cursor': isTyping }"
      >
        {{ title }}
      </h1>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <!-- New Conversation button -->
      <ElButton
        class="new-chat-btn"
        size="small"
        :disabled="!props.isAuthenticated"
        @click="emit('newConversation')"
      >
        <ElIcon class="mr-1"><Plus /></ElIcon>
        {{ isZh ? '新建对话' : 'New Chat' }}
      </ElButton>
      <!-- Close button (panel mode only) -->
      <ElButton
        v-if="!isFullpageMode"
        text
        circle
        size="small"
        @click="emit('close')"
      >
        <ElIcon><Close /></ElIcon>
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
@import './mindmate.css';

/* New Chat button - Swiss Design style (grey, round) */
.new-chat-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}
</style>
