<script setup lang="ts">
/**
 * Editor Status Bar - Session info, node count, diagram type
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { useDiagramStore } from '@/stores'

const diagramStore = useDiagramStore()
const { isZh } = useLanguage()

// Diagram type is used via formattedType
const _diagramType = computed(() => diagramStore.type || '-')
const nodeCount = computed(() => diagramStore.nodeCount)
const sessionId = computed(() => diagramStore.sessionId?.slice(0, 8) || '-')
const selectionCount = computed(() => diagramStore.selectedNodes.length)

// Format diagram type for display
const formattedType = computed(() => {
  if (!diagramStore.type) return '-'
  return diagramStore.type
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
})
</script>

<template>
  <div
    class="editor-status-bar h-6 bg-gray-800 dark:bg-gray-900 text-gray-300 text-xs px-4 flex items-center justify-between"
  >
    <!-- Left: Diagram Info -->
    <div class="flex items-center gap-4">
      <span class="flex items-center gap-1">
        <el-icon :size="12"><Document /></el-icon>
        {{ formattedType }}
      </span>
      <span class="flex items-center gap-1">
        <el-icon :size="12"><Connection /></el-icon>
        {{ nodeCount }} {{ isZh ? '个节点' : 'nodes' }}
      </span>
      <span
        v-if="selectionCount > 0"
        class="flex items-center gap-1 text-primary-400"
      >
        <el-icon :size="12"><Select /></el-icon>
        {{ selectionCount }} {{ isZh ? '已选择' : 'selected' }}
      </span>
    </div>

    <!-- Right: Session Info -->
    <div class="flex items-center gap-4">
      <span class="text-gray-500"> Session: {{ sessionId }} </span>
    </div>
  </div>
</template>

<style scoped>
.editor-status-bar {
  flex-shrink: 0;
}
</style>
