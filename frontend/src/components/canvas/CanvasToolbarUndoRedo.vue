<script setup lang="ts">
import { ElButton, ElTooltip } from 'element-plus'

import { Redo2, Undo2 } from '@lucide/vue'

defineProps<{
  canUndo: boolean
  canRedo: boolean
  undoLabel: string
  redoLabel: string
}>()

const emit = defineEmits<{
  undo: []
  redo: []
}>()
</script>

<template>
  <ElTooltip
    :content="undoLabel"
    placement="bottom"
  >
    <ElButton
      text
      size="small"
      :disabled="!canUndo"
      @click="emit('undo')"
    >
      <Undo2 class="w-4 h-4" />
    </ElButton>
  </ElTooltip>
  <ElTooltip
    :content="redoLabel"
    placement="bottom"
  >
    <ElButton
      text
      size="small"
      :disabled="!canRedo"
      @click="emit('redo')"
    >
      <Redo2 class="w-4 h-4" />
    </ElButton>
  </ElTooltip>
</template>
