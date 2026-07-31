<script setup lang="ts">
/**
 * MaiteMapNode — single curriculum / graph node tile.
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  name: string
  graphType: 'knowledge' | 'thinking'
  status?: string
  masteryLevel?: number
}>()

const { t } = useLanguage()

const statusLabel = computed(() => {
  if (!props.status) {
    return t('maite.map.status.unknown')
  }
  const key = `maite.map.status.${props.status}`
  const translated = t(key)
  return translated === key ? props.status : translated
})
</script>

<template>
  <div
    class="maite-map-node"
    :class="[
      `maite-map-node--${graphType}`,
      status ? `maite-map-node--${status}` : '',
    ]"
  >
    <span class="maite-map-node__type">{{ t(`maite.map.type.${graphType}`) }}</span>
    <span class="maite-map-node__name">{{ name }}</span>
    <span class="maite-map-node__status">{{ statusLabel }}</span>
  </div>
</template>

<style scoped>
.maite-map-node {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
  background: #fff;
  min-height: 72px;
}

.maite-map-node--knowledge {
  border-left: 3px solid #667eea;
}

.maite-map-node--thinking {
  border-left: 3px solid #14b8a6;
}

.maite-map-node--mastered,
.maite-map-node--completed {
  background: #ecfdf5;
}

.maite-map-node--in_progress {
  background: #eff6ff;
}

.maite-map-node__type {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--el-text-color-secondary, #78716c);
}

.maite-map-node__name {
  font-size: 13px;
  font-weight: 600;
}

.maite-map-node__status {
  font-size: 11px;
  color: var(--el-text-color-secondary, #78716c);
}
</style>
