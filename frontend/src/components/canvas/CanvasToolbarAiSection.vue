<script setup lang="ts">
import { ElButton } from 'element-plus'

import { Sparkles, Wand2 } from 'lucide-vue-next'

defineProps<{
  isConceptMap: boolean
  isAIGenerating: boolean
  aiBlockedByCollab: boolean
  conceptGenerationLabel: string
  aiGenerateLabel: string
  aiGeneratingLabel: string
}>()

const emit = defineEmits<{
  conceptGeneration: []
  aiGenerate: []
}>()
</script>

<template>
  <template v-if="isConceptMap">
    <div class="divider" />
    <ElButton
      type="primary"
      size="small"
      class="ai-btn"
      @click="emit('conceptGeneration')"
    >
      <Sparkles class="w-4 h-4" />
      <span>{{ conceptGenerationLabel }}</span>
    </ElButton>
  </template>
  <template v-else>
    <div class="divider" />
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
      <span>{{ isAIGenerating ? aiGeneratingLabel : aiGenerateLabel }}</span>
    </ElButton>
  </template>
</template>
