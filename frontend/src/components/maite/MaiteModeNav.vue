<script setup lang="ts">
/**
 * MaiteModeNav — demo / inquiry / map mode tabs.
 */
import { useLanguage } from '@/composables/core/useLanguage'
import { useMaiteWorkspace } from '@/composables/maite/useMaiteWorkspace'

import type { MaiteMode } from '@/types/maite'

const { t } = useLanguage()
const { mode, setMode } = useMaiteWorkspace()

const modes: MaiteMode[] = ['demo', 'inquiry', 'map']

function modeLabel(value: MaiteMode): string {
  return t(`maite.mode.${value}`)
}

function isActive(value: MaiteMode): boolean {
  return mode.value === value
}
</script>

<template>
  <nav class="maite-mode-nav">
    <button
      v-for="item in modes"
      :key="item"
      type="button"
      class="maite-mode-nav__tab"
      :class="{ 'maite-mode-nav__tab--active': isActive(item) }"
      @click="setMode(item)"
    >
      {{ modeLabel(item) }}
    </button>
  </nav>
</template>

<style scoped>
.maite-mode-nav {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 10px;
  background: var(--el-fill-color-light, #f5f5f4);
}

.maite-mode-nav__tab {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--el-text-color-regular, #57534e);
  transition: background-color 0.15s, color 0.15s;
}

.maite-mode-nav__tab--active {
  background: #fff;
  color: #667eea;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
</style>
