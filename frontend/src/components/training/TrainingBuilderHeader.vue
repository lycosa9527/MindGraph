<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { ElButton, ElIcon } from 'element-plus'

import { useLanguage } from '@/composables'

const { t } = useLanguage()

defineProps<{
  current: string
  showSave?: boolean
  showNew?: boolean
  busy?: boolean
  previewing?: boolean
  readonly?: boolean
  syncLabel?: string
  syncError?: boolean
}>()

const emit = defineEmits<{
  save: []
  info: []
  preview: []
  create: []
}>()
</script>

<template>
  <header class="training-header">
    <nav
      class="training-header__crumb"
      aria-label="breadcrumb"
    >
      <span class="training-header__crumb-root">{{ t('training.title') }}</span>
      <span
        class="training-header__crumb-sep"
        aria-hidden="true"
      >/</span>
      <span class="training-header__crumb-current">{{ current }}</span>
    </nav>
    <div
      v-if="showSave || showNew"
      class="training-header__actions"
    >
      <ElButton
        v-if="showNew"
        size="small"
        class="admin-swiss-btn admin-swiss-btn--primary"
        :loading="busy"
        @click="emit('create')"
      >
        <ElIcon class="training-header__icon"><Plus /></ElIcon>
        {{ t('training.builder.new') }}
      </ElButton>
      <template v-if="showSave">
        <span
          v-if="syncLabel"
          class="training-header__sync"
          :class="{ 'is-error': syncError }"
        >{{ syncLabel }}</span>
        <ElButton
          size="small"
          class="admin-swiss-btn"
          @click="emit('info')"
        >
          {{ t('training.builder.info') }}
        </ElButton>
        <ElButton
          v-if="!readonly"
          size="small"
          class="admin-swiss-btn admin-swiss-btn--primary"
          :loading="busy"
          @click="emit('save')"
        >
          {{ t('training.builder.save') }}
        </ElButton>
        <ElButton
          size="small"
          class="admin-swiss-btn training-header__preview"
          :class="{ 'is-previewing': previewing }"
          @click="emit('preview')"
        >
          {{ previewing ? t('training.builder.previewExit') : t('training.builder.preview') }}
        </ElButton>
      </template>
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
.training-header__crumb {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
}
.training-header__crumb-root {
  color: #78716c;
}
.training-header__crumb-sep {
  color: #a8a29e;
}
.training-header__crumb-current {
  overflow: hidden;
  font-weight: 600;
  color: #1c1917;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.training-header__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.training-header__sync {
  color: #78716c;
  font-size: 0.75rem;
  font-weight: 600;
}
.training-header__sync.is-error {
  color: #b91c1c;
}
.training-header__icon {
  margin-right: 0.25rem;
}
.training-header__preview.el-button {
  --el-button-bg-color: #15803d;
  --el-button-border-color: #15803d;
  --el-button-text-color: #fafaf9;
  --el-button-hover-bg-color: #166534;
  --el-button-hover-border-color: #166534;
  --el-button-hover-text-color: #fafaf9;
  --el-button-active-bg-color: #14532d;
  --el-button-active-border-color: #14532d;
}
.training-header__preview.is-previewing.el-button {
  --el-button-bg-color: #166534;
  --el-button-border-color: #166534;
}
</style>
