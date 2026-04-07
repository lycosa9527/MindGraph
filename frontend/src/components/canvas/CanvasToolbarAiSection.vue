<script setup lang="ts">
import { ElButton, ElTooltip } from 'element-plus'

import { Sparkles, Wand2 } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    compact?: boolean
    isConceptMap: boolean
    isAIGenerating: boolean
    aiBlockedByCollab: boolean
    conceptGenerationLabel: string
    aiGenerateLabel: string
    aiGeneratingLabel: string
  }>(),
  { compact: false }
)

const emit = defineEmits<{
  conceptGeneration: []
  aiGenerate: []
}>()
</script>

<template>
  <template v-if="isConceptMap">
    <div class="divider" />
    <ElTooltip
      :content="conceptGenerationLabel"
      placement="bottom"
      :disabled="!compact"
    >
      <ElButton
        type="primary"
        size="small"
        class="ai-btn"
        @click="emit('conceptGeneration')"
      >
        <Sparkles class="w-4 h-4" />
        <span v-if="!compact">{{ conceptGenerationLabel }}</span>
      </ElButton>
    </ElTooltip>
  </template>
  <template v-else>
    <div class="divider" />
    <ElTooltip
      :content="isAIGenerating ? aiGeneratingLabel : aiGenerateLabel"
      placement="bottom"
      :disabled="!compact"
    >
      <ElButton
        type="primary"
        size="small"
        class="ai-btn"
        :class="{ 'ai-btn--generating': isAIGenerating }"
        :disabled="isAIGenerating || aiBlockedByCollab"
        @click="emit('aiGenerate')"
      >
        <Wand2
          class="w-4 h-4 shrink-0"
          :class="isAIGenerating ? 'opacity-30' : ''"
          aria-hidden="true"
        />
        <span v-if="!compact">{{ isAIGenerating ? aiGeneratingLabel : aiGenerateLabel }}</span>
      </ElButton>
    </ElTooltip>
  </template>
</template>
