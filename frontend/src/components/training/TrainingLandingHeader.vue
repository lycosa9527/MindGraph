<script setup lang="ts">
import { computed } from 'vue'

import { ElButton, ElOption, ElSelect } from 'element-plus'

import { useLanguage } from '@/composables'
import type { TrainingOrgRow, TrainingReady } from '@/types/training'

const SCHOOL_SELECT_POPPER_CLASS = 'admin-swiss-school-select-popper'

const { t } = useLanguage()

const props = defineProps<{
  orgs: TrainingOrgRow[]
  selectedOrgId: number | null
  ready: TrainingReady | null
  busy: boolean
  canControl: boolean
  isLive: boolean
  isPaused: boolean
  isForeign: boolean
}>()

const emit = defineEmits<{
  search: [query: string]
  selectOrg: [orgId: number | null]
  start: []
  pause: []
  resume: []
  end: []
  takeover: []
}>()

const startMode = computed(() => {
  if (props.canControl) return 'stop'
  if (props.selectedOrgId != null && !props.isForeign) return 'ready'
  return 'idle'
})
const orgLocked = computed(() => props.canControl || props.isForeign)

function onOrgChange(value: number | string | null): void {
  if (value == null || value === '') {
    emit('selectOrg', null)
    return
  }
  emit('selectOrg', Number(value))
}

function onStartStop(): void {
  if (startMode.value === 'stop') {
    emit('end')
    return
  }
  if (startMode.value === 'ready') {
    emit('start')
  }
}
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
      >
        /
      </span>
      <span class="training-header__crumb-current">{{ t('training.courses') }}</span>
    </nav>
    <div class="training-header__actions">
      <p
        v-if="ready"
        class="training-header__ready"
      >
        {{ t('training.teacherTotal', { n: ready.teacher_total }) }} ·
        {{ t('training.onlineNow', { n: ready.online_now }) }}
      </p>
      <ElSelect
        class="admin-swiss-select admin-swiss-select--school"
        :model-value="selectedOrgId"
        filterable
        remote
        clearable
        size="small"
        :disabled="busy || orgLocked"
        :placeholder="t('training.searchOrg')"
        :popper-class="SCHOOL_SELECT_POPPER_CLASS"
        :remote-method="(query: string) => emit('search', query)"
        @change="onOrgChange"
      >
        <ElOption
          v-for="org in orgs"
          :key="org.id"
          :label="org.name"
          :value="org.id"
        >
          <span class="admin-swiss-school-option__label">{{ org.name }}</span>
        </ElOption>
      </ElSelect>
      <ElButton
        size="small"
        class="training-start-btn"
        :class="`training-start-btn--${startMode}`"
        :loading="busy"
        :disabled="busy || startMode === 'idle'"
        @click="onStartStop"
      >
        {{ startMode === 'stop' ? t('training.stop') : t('training.start') }}
      </ElButton>
      <ElButton
        v-if="isForeign"
        size="small"
        class="admin-swiss-btn"
        :loading="busy"
        :disabled="busy"
        @click="emit('takeover')"
      >
        {{ t('training.takeover') }}
      </ElButton>
      <ElButton
        v-if="canControl && isLive"
        size="small"
        class="admin-swiss-btn"
        :loading="busy"
        :disabled="busy"
        @click="emit('pause')"
      >
        {{ t('training.pause') }}
      </ElButton>
      <ElButton
        v-if="canControl && isPaused"
        size="small"
        class="admin-swiss-btn"
        :loading="busy"
        :disabled="busy"
        @click="emit('resume')"
      >
        {{ t('training.resume') }}
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
  flex-shrink: 0;
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
  min-width: 0;
  align-items: center;
  gap: 0.5rem;
}
.training-header__ready {
  margin: 0;
  color: #78716c;
  font-size: 0.75rem;
  white-space: nowrap;
}
.training-start-btn.el-button {
  min-width: 4.25rem;
  min-height: 28px;
  padding: 0 0.875rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 500;
}
.training-start-btn--idle.el-button {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-text-color: #a8a29e;
  --el-button-disabled-bg-color: #e7e5e4;
  --el-button-disabled-border-color: #d6d3d1;
  --el-button-disabled-text-color: #a8a29e;
}
.training-start-btn--ready.el-button {
  --el-button-bg-color: #16a34a;
  --el-button-border-color: #16a34a;
  --el-button-text-color: #fff;
  --el-button-hover-bg-color: #15803d;
  --el-button-hover-border-color: #15803d;
  --el-button-hover-text-color: #fff;
  --el-button-active-bg-color: #166534;
  --el-button-active-border-color: #166534;
}
.training-start-btn--stop.el-button {
  --el-button-bg-color: #dc2626;
  --el-button-border-color: #dc2626;
  --el-button-text-color: #fff;
  --el-button-hover-bg-color: #b91c1c;
  --el-button-hover-border-color: #b91c1c;
  --el-button-hover-text-color: #fff;
  --el-button-active-bg-color: #991b1b;
  --el-button-active-border-color: #991b1b;
}
</style>
