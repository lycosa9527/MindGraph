<script setup lang="ts">
import { ElButton, ElTooltip } from 'element-plus'

import { RotateCcw, RotateCw } from 'lucide-vue-next'

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
      <RotateCw class="w-4 h-4" />
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
      <RotateCcw class="w-4 h-4" />
    </ElButton>
  </ElTooltip>
</template>
