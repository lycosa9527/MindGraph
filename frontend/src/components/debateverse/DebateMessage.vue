<script setup lang="ts">
/**
 * DebateMessage - Individual speech bubble
 */
import { computed, ref } from 'vue'

import { ElButton } from 'element-plus'

import { ChevronDown, ChevronUp } from 'lucide-vue-next'

import MarkdownIt from 'markdown-it'

import type { DebateMessage as DebateMessageType } from '@/stores/debateverse'
import { useDebateVerseStore } from '@/stores/debateverse'

const props = defineProps<{
  message: DebateMessageType
}>()

const store = useDebateVerseStore()

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
</script>

<template>
  <div class="debate-message">
    <!-- Speech Bubble -->
    <div
      class="speech-bubble p-3 rounded-lg shadow-sm"
      :class="{
        'bg-green-50 border border-green-200': participant?.side === 'affirmative',
        'bg-red-50 border border-red-200': participant?.side === 'negative',
        'bg-gray-50 border border-gray-200': !participant?.side,
      }"
    >
      <!-- Header -->
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <span class="text-xs font-medium text-gray-700">
            {{ participant?.name }}
          </span>
          <span class="text-xs text-gray-500">
            {{ message.stage }} (Round {{ message.round_number }})
          </span>
        </div>
      </div>

      <!-- Content -->
      <div
        class="message-content text-sm text-gray-900 prose prose-sm max-w-none"
        v-html="renderedContent"
      />

      <!-- Thinking (Collapsible) -->
      <div
        v-if="hasThinking"
        class="mt-2 pt-2 border-t border-gray-200"
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
          {{ thinkingCollapsed ? '显示思考过程' : '隐藏思考过程' }}
        </ElButton>
        <div
          v-if="!thinkingCollapsed"
          class="mt-2 text-xs text-gray-600 italic"
        >
          {{ message.thinking }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.speech-bubble {
  position: relative;
}

.speech-bubble::before {
  content: '';
  position: absolute;
  bottom: -8px;
  left: 20px;
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 8px solid currentColor;
}

.prose {
  color: inherit;
}

.prose :deep(p) {
  margin: 0.5em 0;
}

.prose :deep(strong) {
  font-weight: 600;
}
</style>
