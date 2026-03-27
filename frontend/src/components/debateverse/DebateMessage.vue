<script setup lang="ts">
/**
 * DebateMessage - ChatGPT-style message with avatar and role on left
 */
import { computed, ref } from 'vue'

import { ElButton } from 'element-plus'

import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import MarkdownIt from 'markdown-it'

import deepseekAvatar from '@/assets/deepseek-avatar.png'
import doubaoAvatar from '@/assets/doubao-avatar.png'
import judgeAvatar from '@/assets/judge-avatar.png'
import kimiAvatar from '@/assets/kimi-avatar.png'
// Import avatar images
import qwenAvatar from '@/assets/qwen-avatar.png'
import userAvatar from '@/assets/user-avatar.png'
import { useLanguage } from '@/composables/core/useLanguage'
import type { DebateMessage as DebateMessageType } from '@/stores/debateverse'
import { useDebateVerseStore } from '@/stores/debateverse'

const props = defineProps<{
  message: DebateMessageType
}>()

const store = useDebateVerseStore()
const { t } = useLanguage()

// ============================================================================
// State
// ============================================================================

const thinkingCollapsed = ref(true)

// ============================================================================
// Computed
// ============================================================================

const participant = computed(() =>
  store.participants.find((p) => p.id === props.message.participant_id)
)

const avatarImage = computed(() => {
  if (!participant.value) return userAvatar

  // User avatar (when not AI)
  if (!participant.value.is_ai) {
    return userAvatar
  }

  // Judge avatar
  if (participant.value.role === 'judge') {
    return judgeAvatar
  }

  // LLM avatars based on model_id
  const avatarMap: Record<string, string> = {
    qwen: qwenAvatar,
    deepseek: deepseekAvatar,
    doubao: doubaoAvatar,
    kimi: kimiAvatar,
  }

  return avatarMap[participant.value.model_id || 'qwen'] || qwenAvatar
})

const modelDisplayName = computed(() => {
  if (!participant.value?.model_id) return ''
  const names: Record<string, string> = {
    qwen: 'Qwen',
    doubao: 'Doubao',
    deepseek: 'DeepSeek',
    kimi: 'Kimi',
  }
  return names[participant.value.model_id] || participant.value.model_id
})

const roleDisplayName = computed(() => {
  if (!participant.value?.role) return ''

  if (participant.value.role === 'judge') {
    return t('debateverse.message.judge')
  }

  const roleKeys: Record<string, string> = {
    affirmative_1: 'debateverse.message.roleAffirmative1',
    affirmative_2: 'debateverse.message.roleAffirmative2',
    negative_1: 'debateverse.message.roleNegative1',
    negative_2: 'debateverse.message.roleNegative2',
  }

  const key = roleKeys[participant.value.role]
  return key ? t(key) : participant.value.role
})

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return md.render(props.message.content)
})

const hasThinking = computed(() => props.message.thinking && props.message.thinking.length > 0)

const isStreaming = computed(() => props.message.is_streaming ?? false)

const isAffirmative = computed(() => participant.value?.side === 'affirmative')
const isNegative = computed(() => participant.value?.side === 'negative')
const isJudge = computed(() => participant.value?.role === 'judge' || !participant.value?.side)
</script>

<template>
  <div
    class="debate-message flex gap-4 items-start py-4 px-4 hover:bg-gray-50 transition-colors w-full"
    :class="{
      'flex-row justify-start': isAffirmative || isJudge,
      'flex-row justify-end': isNegative,
    }"
  >
    <!-- Avatar Section -->
    <div
      class="flex-shrink-0 flex flex-col items-center gap-1"
      :class="{ 'order-2': isNegative, 'order-1': isAffirmative || isJudge }"
    >
      <img
        :src="avatarImage"
        :alt="participant?.name || 'Participant'"
        class="w-8 h-8 rounded-lg object-cover"
      />
      <div class="text-xs text-center max-w-[60px]">
        <div
          v-if="participant?.is_ai && modelDisplayName"
          class="font-semibold text-blue-600"
        >
          {{ modelDisplayName }}
        </div>
        <div
          v-if="roleDisplayName"
          class="text-gray-600 mt-0.5"
        >
          {{ roleDisplayName }}
        </div>
      </div>
    </div>

    <!-- Message Content Section -->
    <div
      class="flex-1 min-w-0 flex"
      :class="{
        'order-1 justify-end items-end': isNegative,
        'order-2 justify-start': isAffirmative || isJudge,
      }"
    >
      <div
        class="message-box rounded-lg px-4 py-3 max-w-[80%] shadow-sm"
        :class="{
          'bg-green-50 border border-green-200': isAffirmative,
          'bg-red-50 border border-red-200 ml-auto': isNegative,
          'bg-gray-50 border border-gray-200': isJudge,
        }"
      >
        <!-- Header with name and stage info -->
        <div class="flex items-center gap-2 mb-2">
          <span class="text-sm font-medium text-gray-900">
            {{ participant?.name }}
          </span>
          <span class="text-xs text-gray-500">
            {{ message.stage }} · Round {{ message.round_number }}
          </span>
        </div>

        <!-- Content -->
        <div
          class="message-content text-sm text-gray-800 prose prose-sm max-w-none"
          :class="{ 'opacity-70': isStreaming }"
          v-html="renderedContent"
        />

        <!-- Thinking (Collapsible) -->
        <div
          v-if="hasThinking"
          class="mt-3 pt-3 border-t border-gray-200"
        >
          <ElButton
            text
            size="small"
            @click="thinkingCollapsed = !thinkingCollapsed"
          >
            <component
              :is="thinkingCollapsed ? ChevronDown : ChevronUp"
              class="w-4 h-4 mr-1"
            />
            {{
              thinkingCollapsed
                ? t('debateverse.message.showThinking')
                : t('debateverse.message.hideThinking')
            }}
          </ElButton>
          <div
            v-if="!thinkingCollapsed"
            class="mt-2 text-xs text-gray-600 italic whitespace-pre-wrap"
          >
            {{ message.thinking }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prose {
  color: inherit;
}

.prose :deep(p) {
  margin: 0.5em 0;
}

.prose :deep(p:first-child) {
  margin-top: 0;
}

.prose :deep(p:last-child) {
  margin-bottom: 0;
}

.prose :deep(strong) {
  font-weight: 600;
}

.prose :deep(ul),
.prose :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.prose :deep(li) {
  margin: 0.25em 0;
}

.prose :deep(code) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 0.125em 0.25em;
  border-radius: 0.25em;
  font-size: 0.9em;
}

.prose :deep(pre) {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 0.75em;
  border-radius: 0.5em;
  overflow-x: auto;
  margin: 0.5em 0;
}

.prose :deep(pre code) {
  background-color: transparent;
  padding: 0;
}
</style>
