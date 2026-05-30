<script setup lang="ts">
/**
 * School selector for admins previewing the school dashboard.
 */
import { computed, onMounted } from 'vue'

import { useSchoolDashboardOrgPicker } from '@/composables/school/useSchoolDashboardOrgPicker'
import { useLanguage } from '@/composables'

const SELECT_FONT = '500 13px ui-sans-serif, system-ui, sans-serif'
const SELECT_MIN_WIDTH_PX = 72
const SELECT_MAX_WIDTH_PX = 168
const SCHOOL_SELECT_POPPER_CLASS = 'admin-swiss-school-select-popper'
/** Left/right padding inside the pill + caret area. */
const SELECT_HORIZONTAL_PAD_PX = 40

function measureTextWidthPx(text: string): number {
  if (text.length === 0) {
    return 0
  }
  if (typeof document === 'undefined') {
    return text.length * 8
  }
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return text.length * 8
  }
  ctx.font = SELECT_FONT
  return Math.ceil(ctx.measureText(text).width)
}

withDefaults(
  defineProps<{
    /** Hide the "View school" label (management panel header). */
    compact?: boolean
  }>(),
  { compact: false }
)

const { t } = useLanguage()
const { organizations, selectedOrgId, showPicker, loadOrganizations } = useSchoolDashboardOrgPicker()

const selectDisplayText = computed(() => {
  if (selectedOrgId.value == null) {
    return t('admin.selectSchool')
  }
  const match = organizations.value.find((org) => org.id === selectedOrgId.value)
  return match?.name ?? t('admin.selectSchool')
})

const selectWidthStyle = computed(() => {
  const content = measureTextWidthPx(selectDisplayText.value) + SELECT_HORIZONTAL_PAD_PX
  const clamped = Math.min(
    SELECT_MAX_WIDTH_PX,
    Math.max(SELECT_MIN_WIDTH_PX, content)
  )
  return { width: `${clamped}px` }
})

onMounted(() => {
  void loadOrganizations()
})
</script>

<template>
  <div
    v-if="showPicker"
    class="school-dashboard-org-picker flex items-center gap-1.5 shrink-0 min-w-0"
  >
    <span
      v-if="compact"
      class="admin-swiss-glyph"
      aria-hidden="true"
    >
      ◇
    </span>
    <span
      v-else
      class="text-stone-500 text-xs font-medium uppercase tracking-wide whitespace-nowrap"
    >
      {{ t('admin.viewSchool') }}
    </span>
    <el-select
      v-model="selectedOrgId"
      filterable
      :placeholder="t('admin.selectSchool')"
      size="small"
      class="admin-swiss-select admin-swiss-select--school"
      :style="selectWidthStyle"
      :popper-class="SCHOOL_SELECT_POPPER_CLASS"
    >
      <el-option
        v-for="org in organizations"
        :key="org.id"
        :label="org.name"
        :value="org.id"
      >
        <span class="admin-swiss-school-option__label">{{ org.name }}</span>
      </el-option>
    </el-select>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
