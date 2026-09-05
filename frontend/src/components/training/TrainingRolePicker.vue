<script setup lang="ts">
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables'
import {
  TRAINING_ROLES,
  trainingRoleThumb,
  type TrainingRoleDef,
} from '@/config/trainingRoles'

const emit = defineEmits<{
  pick: [role: string]
}>()

const { t } = useLanguage()
const hoveredId = ref<string | null>(null)
const preview = computed(
  (): TrainingRoleDef | undefined => TRAINING_ROLES.find((role) => role.id === hoveredId.value)
)

function showPreview(id: string): void {
  hoveredId.value = id
}

function hidePreview(): void {
  hoveredId.value = null
}
</script>

<template>
  <div
    class="role-picker"
    @mouseleave="hidePreview"
  >
    <div
      class="role-picker__grid"
      role="listbox"
      :aria-label="t('training.builder.toolRoles')"
    >
      <button
        v-for="role in TRAINING_ROLES"
        :key="role.id"
        type="button"
        class="role-picker__cell"
        role="option"
        :aria-selected="hoveredId === role.id"
        :title="t(role.labelKey)"
        @mouseenter="showPreview(role.id)"
        @focus="showPreview(role.id)"
        @click="emit('pick', role.id)"
      >
        <img
          class="role-picker__thumb"
          :src="trainingRoleThumb(role.id)"
          :alt="t(role.labelKey)"
        >
        <span class="role-picker__name">{{ t(role.labelKey) }}</span>
      </button>
    </div>
    <div
      v-if="preview"
      class="role-picker__preview"
    >
      <div class="role-picker__card">
        <img
          class="role-picker__anim"
          :src="trainingRoleThumb(preview.id)"
          :alt="t(preview.labelKey)"
        >
        <p class="role-picker__caption">{{ t(preview.labelKey) }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.role-picker {
  position: relative;
  width: 18.5rem;
}
.role-picker__grid {
  display: grid;
  max-height: 18rem;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.35rem;
  overflow: auto;
}
.role-picker__cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  border: 1px solid #e7e5e4;
  background: #fff;
  padding: 0.25rem 0.15rem 0.3rem;
  cursor: pointer;
}
.role-picker__cell:hover,
.role-picker__cell:focus-visible,
.role-picker__cell[aria-selected='true'] {
  border-color: #1c1917;
}
.role-picker__thumb {
  width: 3.4rem;
  height: 3.4rem;
  object-fit: contain;
}
.role-picker__name {
  overflow: hidden;
  color: #57534e;
  font-size: 0.62rem;
  line-height: 1.2;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}
.role-picker__preview {
  position: absolute;
  top: 0;
  left: 100%;
  z-index: 2;
  padding-left: 0.45rem;
}
.role-picker__card {
  display: flex;
  width: 10.5rem;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid #e7e5e4;
  background:
    linear-gradient(45deg, #f5f5f4 25%, transparent 25%) 0 0 / 0.7rem 0.7rem,
    linear-gradient(-45deg, #f5f5f4 25%, transparent 25%) 0 0.35rem / 0.7rem 0.7rem,
    linear-gradient(45deg, transparent 75%, #f5f5f4 75%) 0.35rem -0.35rem / 0.7rem 0.7rem,
    linear-gradient(-45deg, transparent 75%, #f5f5f4 75%) -0.35rem 0 / 0.7rem 0.7rem,
    #fff;
  padding: 0.55rem 0.5rem 0.45rem;
  box-shadow: 0 10px 28px rgb(28 25 23 / 0.12);
}
.role-picker__anim {
  width: 9.4rem;
  height: 9.4rem;
  object-fit: contain;
}
.role-picker__caption {
  margin: 0;
  color: #1c1917;
  font-size: 0.72rem;
  font-weight: 650;
  text-align: center;
}
</style>
