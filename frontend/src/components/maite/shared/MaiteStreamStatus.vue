<script setup lang="ts">
/**
 * MaiteStreamStatus — mentor SSE status indicator.
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  status?: string
  preview?: string
  streaming?: boolean
}>()

const emit = defineEmits<{
  stop: []
}>()

const { t } = useLanguage()

const label = computed(() => {
  if (!props.streaming) {
    return ''
  }
  if (props.status === 'fallback') {
    return t('maite.stream.fallback')
  }
  if (props.status === 'receiving' || props.preview) {
    return t('maite.stream.receiving')
  }
  if (props.status && props.status !== 'waiting_llm') {
    return props.status
  }
  return t('maite.stream.working')
})

const previewText = computed(() => {
  const text = props.preview?.trim() ?? ''
  if (text.length <= 600) {
    return text
  }
  return `${text.slice(-600)}`
})
</script>

<template>
  <div v-if="streaming" class="maite-stream-status">
    <span class="maite-stream-status__dot" />
    <span class="maite-stream-status__label">{{ label }}</span>
    <button type="button" class="maite-stream-status__stop" @click="emit('stop')">
      {{ t('maite.stream.stop') }}
    </button>
    <p v-if="previewText" class="maite-stream-status__preview">{{ previewText }}</p>
  </div>
</template>

<style scoped>
.maite-stream-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light, #f5f5f4);
  color: var(--el-text-color-regular, #57534e);
  font-size: 13px;
}

.maite-stream-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #667eea;
  animation: maite-pulse 1.2s ease-in-out infinite;
}

.maite-stream-status__stop {
  margin-left: auto;
  border: none;
  background: transparent;
  color: #667eea;
  cursor: pointer;
  font-size: 13px;
}

.maite-stream-status__preview {
  flex-basis: 100%;
  margin: 0;
  max-height: 160px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.45;
  color: var(--el-text-color-secondary, #78716c);
}

@keyframes maite-pulse {
  0%,
  100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}
</style>
