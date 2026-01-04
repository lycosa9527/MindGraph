<script setup lang="ts">
/**
 * Diagram Card - Individual diagram type card
 */
import type { DiagramType } from '@/types'

defineProps<{
  type: DiagramType
  name: string
  description: string
  icon: string
}>()

const emit = defineEmits<{
  (e: 'click'): void
}>()

// Icon mapping for diagram types
const iconColors: Record<string, string> = {
  bubble: 'bg-blue-500',
  circle: 'bg-purple-500',
  'double-bubble': 'bg-indigo-500',
  tree: 'bg-green-500',
  brace: 'bg-teal-500',
  flow: 'bg-orange-500',
  'multi-flow': 'bg-red-500',
  bridge: 'bg-pink-500',
  concept: 'bg-cyan-500',
  mindmap: 'bg-amber-500',
}
</script>

<template>
  <div
    class="diagram-card group cursor-pointer"
    @click="emit('click')"
  >
    <div
      class="card-inner bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 hover:border-primary-400 dark:hover:border-primary-500 hover:shadow-lg transition-all duration-200"
    >
      <!-- Icon -->
      <div
        class="w-12 h-12 rounded-lg mb-3 flex items-center justify-center"
        :class="iconColors[icon] || 'bg-gray-500'"
      >
        <el-icon
          :size="24"
          class="text-white"
        >
          <component :is="getIconComponent()" />
        </el-icon>
      </div>

      <!-- Name -->
      <h3 class="font-medium text-gray-800 dark:text-white mb-1 text-sm">
        {{ name }}
      </h3>

      <!-- Description -->
      <p class="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
        {{ description }}
      </p>
    </div>
  </div>
</template>

<script lang="ts">
// Helper function for icon mapping
function getIconComponent(): string {
  // Default icon, can be extended based on diagram type
  return 'Document'
}
</script>

<style scoped>
.diagram-card .card-inner {
  transform: translateY(0);
}

.diagram-card:hover .card-inner {
  transform: translateY(-2px);
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
