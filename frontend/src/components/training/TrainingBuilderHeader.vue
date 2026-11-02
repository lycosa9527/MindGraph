<script setup lang="ts">
import { computed } from 'vue'

import { ElButton, ElIcon } from 'element-plus'

import { Plus } from '@element-plus/icons-vue'

import { PanelLeftClose, PanelLeftOpen } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useUIStore } from '@/stores/ui'

defineProps<{
  current: string
  showNew?: boolean
  busy?: boolean
}>()

const emit = defineEmits<{
  create: []
}>()

const { t } = useLanguage()
const uiStore = useUIStore()
const sidebarCollapsed = computed(() => uiStore.sidebarCollapsed)
const sidebarToggleLabel = computed(() =>
  sidebarCollapsed.value ? t('sidebar.expandSidebar') : t('sidebar.collapseSidebar')
)
</script>

<template>
  <header class="training-header">
    <div class="training-header__lead">
      <button
        type="button"
        class="training-header__sidebar"
        :title="sidebarToggleLabel"
        :aria-label="sidebarToggleLabel"
        @click="uiStore.toggleSidebar()"
      >
        <PanelLeftOpen
          v-if="sidebarCollapsed"
          :size="18"
          aria-hidden="true"
        />
        <PanelLeftClose
          v-else
          :size="18"
          aria-hidden="true"
        />
      </button>
      <h1 class="training-header__title">{{ current }}</h1>
    </div>
    <div
      v-if="showNew"
      class="training-header__actions"
    >
      <ElButton
        size="small"
        class="admin-swiss-btn admin-swiss-btn--primary"
        :loading="busy"
        @click="emit('create')"
      >
        <ElIcon class="training-header__icon"><Plus /></ElIcon>
        <I18nText k="training.builder.new" />
      </ElButton>
    </div>
  </header>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.training-header {
  display: flex;
  height: 3.5rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-bottom: 1px solid #e7e5e4;
  background: #fff;
  padding: 0 1rem;
}
.training-header__lead {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.35rem;
}
.training-header__sidebar {
  display: flex;
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #57534e;
  cursor: pointer;
}
.training-header__sidebar:hover {
  background: #f5f5f4;
  color: #1c1917;
}
.training-header__title {
  margin: 0;
  overflow: hidden;
  color: #1c1917;
  font-size: 0.875rem;
  font-weight: 650;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.training-header__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.training-header__icon {
  margin-right: 0.25rem;
}
</style>
