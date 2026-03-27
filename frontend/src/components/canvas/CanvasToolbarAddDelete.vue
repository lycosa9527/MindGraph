<script setup lang="ts">
import { ElButton, ElTooltip } from 'element-plus'

import { Plus, Trash2 } from 'lucide-vue-next'

defineProps<{
  isMultiFlowMap: boolean
  isBridgeMap: boolean
  addCauseLabel: string
  addEffectLabel: string
  addAnalogyPairLabel: string
  addPairShort: string
  addNodeLabel: string
  addShort: string
  deleteNodeLabel: string
  deleteShort: string
}>()

const emit = defineEmits<{
  addCause: []
  addEffect: []
  addNode: []
  deleteNode: []
}>()
</script>

<template>
  <template v-if="isMultiFlowMap">
    <ElTooltip
      :content="addCauseLabel"
      placement="bottom"
    >
      <ElButton
        text
        size="small"
        @click="emit('addCause')"
      >
        <Plus class="w-4 h-4" />
        <span>{{ addCauseLabel }}</span>
      </ElButton>
    </ElTooltip>
    <ElTooltip
      :content="addEffectLabel"
      placement="bottom"
    >
      <ElButton
        text
        size="small"
        @click="emit('addEffect')"
      >
        <Plus class="w-4 h-4" />
        <span>{{ addEffectLabel }}</span>
      </ElButton>
    </ElTooltip>
  </template>

  <template v-else-if="isBridgeMap">
    <ElTooltip
      :content="addAnalogyPairLabel"
      placement="bottom"
    >
      <ElButton
        text
        size="small"
        @click="emit('addNode')"
      >
        <Plus class="w-4 h-4" />
        <span>{{ addPairShort }}</span>
      </ElButton>
    </ElTooltip>
  </template>

  <ElTooltip
    v-else
    :content="addNodeLabel"
    placement="bottom"
  >
    <ElButton
      text
      size="small"
      @click="emit('addNode')"
    >
      <Plus class="w-4 h-4" />
      <span>{{ addShort }}</span>
    </ElButton>
  </ElTooltip>
  <ElTooltip
    :content="deleteNodeLabel"
    placement="bottom"
  >
    <ElButton
      text
      size="small"
      @click="emit('deleteNode')"
    >
      <Trash2 class="w-4 h-4" />
      <span>{{ deleteShort }}</span>
    </ElButton>
  </ElTooltip>
</template>
