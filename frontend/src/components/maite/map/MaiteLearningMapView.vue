<script setup lang="ts">
/**
 * MaiteLearningMapView — curriculum modules with API graph node states.
 */
import { computed, onMounted } from 'vue'

import MaiteMapNode from '@/components/maite/map/MaiteMapNode.vue'
import { MAITE_MAP_CURRICULUM } from '@/data/maite/mapCurriculum'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMaiteMap } from '@/composables/maite/useMaiteMap'
import { eventBus } from '@/composables/core/useEventBus'

import type { MaiteGraphNode } from '@/types/maite'

const { t } = useLanguage()
const { graph, loading, refreshGraph } = useMaiteMap()

onMounted(() => {
  eventBus.emit('maite:map_refresh_requested', {})
})

const nodeStateMap = computed(() => {
  const map = new Map<string, MaiteGraphNode>()
  for (const node of graph.value?.knowledge_nodes ?? []) {
    map.set(node.node_key, node)
  }
  for (const node of graph.value?.thinking_nodes ?? []) {
    map.set(node.node_key, node)
  }
  return map
})

function resolveStatus(nodeKey: string): string | undefined {
  return nodeStateMap.value.get(nodeKey)?.status
}
</script>

<template>
  <div class="maite-learning-map-view">
    <header class="maite-learning-map-view__header">
      <h3>{{ t('maite.map.title') }}</h3>
      <button type="button" :disabled="loading" @click="refreshGraph">
        {{ loading ? t('maite.map.refreshing') : t('maite.map.refresh') }}
      </button>
    </header>

    <section v-for="module in MAITE_MAP_CURRICULUM" :key="module.id" class="maite-learning-map-view__module">
      <header>
        <h4>{{ module.title }}</h4>
        <span>{{ module.gradeBand }}</span>
      </header>
      <div class="maite-learning-map-view__grid">
        <MaiteMapNode
          v-for="node in module.knowledgeNodes"
          :key="`${module.id}-k-${node.key}`"
          :name="node.name"
          graph-type="knowledge"
          :status="resolveStatus(node.key)"
        />
        <MaiteMapNode
          v-for="node in module.thinkingNodes"
          :key="`${module.id}-t-${node.key}`"
          :name="node.name"
          graph-type="thinking"
          :status="resolveStatus(node.key)"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.maite-learning-map-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.maite-learning-map-view__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.maite-learning-map-view__header h3 {
  margin: 0;
  font-size: 15px;
}

.maite-learning-map-view__header button {
  padding: 6px 12px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
}

.maite-learning-map-view__module {
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
}

.maite-learning-map-view__module header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
}

.maite-learning-map-view__module h4 {
  margin: 0;
  font-size: 14px;
}

.maite-learning-map-view__module span {
  font-size: 12px;
  color: var(--el-text-color-secondary, #78716c);
}

.maite-learning-map-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}
</style>
