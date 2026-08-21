<script setup lang="ts">
import { ElButton, ElTooltip } from 'element-plus'

import { Sparkles } from '@lucide/vue'

withDefaults(
  defineProps<{
    compact?: boolean
    conceptGenerationLabel: string
  }>(),
  { compact: false }
)

const emit = defineEmits<{
  conceptGeneration: []
}>()
</script>

<template>
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
