<script setup lang="ts">
/**
 * 系统设置 → 用户下拉列表 — add, rename, delete, link a course, preview the tour.
 */
import { computed, ref } from 'vue'

import { ElMessageBox } from 'element-plus'

import { useQueryClient } from '@tanstack/vue-query'

import TrainingCourseWalkthrough from '@/components/training/TrainingCourseWalkthrough.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  type UserDropdownCatalog,
  type UserDropdownItemRow,
  createUserDropdownItem,
  deleteUserDropdownItem,
  patchUserDropdownItem,
  useAdminUserDropdown,
} from '@/composables/admin/userDropdownApi'
import { adminKeys } from '@/composables/queries/adminKeys'
import type { TrainingCourse } from '@/types/training'
import { fetchTrainingCourse } from '@/utils/trainingApi'

const { t } = useLanguage()
const notify = useNotifications()
const queryClient = useQueryClient()
const { can, isTabReadOnly } = useAdminAccess()

const catalogQuery = useAdminUserDropdown()
const draft = ref('')
const labelDraft = ref<Record<string, string>>({})
const saving = ref(false)
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewCourse = ref<TrainingCourse | null>(null)

const canEdit = computed(() => can('tab.settings.user_dropdown') && !isTabReadOnly('settings'))
const catalog = computed(() => catalogQuery.data.value)
const items = computed(() => catalog.value?.items ?? [])
const courses = computed(() => catalog.value?.courses ?? [])
const loading = computed(() => catalogQuery.isFetching.value && !catalog.value)
const loadError = computed(() => catalogQuery.error.value?.message ?? null)

function isRow(row: unknown): row is UserDropdownItemRow {
  if (!row || typeof row !== 'object') return false
  const candidate = row as Record<string, unknown>
  return typeof candidate.id === 'string' && typeof candidate.label === 'string'
}

function applyCatalog(next: UserDropdownCatalog): void {
  queryClient.setQueryData(adminKeys.userDropdown(), next)
}

async function addItem(): Promise<void> {
  const label = draft.value.trim()
  if (!label || saving.value) return
  saving.value = true
  try {
    applyCatalog(await createUserDropdownItem(label))
    draft.value = ''
    notify.successKey('admin.userDropdown.addOk')
  } catch {
    notify.errorKey('admin.userDropdown.saveFail')
  } finally {
    saving.value = false
  }
}

function labelOf(row: UserDropdownItemRow): string {
  return labelDraft.value[row.id] ?? row.label
}

function onLabelInput(row: UserDropdownItemRow, value: string | number): void {
  labelDraft.value = { ...labelDraft.value, [row.id]: String(value) }
}

async function rename(row: unknown, label: string | number): Promise<void> {
  if (!isRow(row) || !canEdit.value) return
  const next = String(label).trim()
  if (!next || next === row.label) {
    const rest = { ...labelDraft.value }
    delete rest[row.id]
    labelDraft.value = rest
    return
  }
  try {
    applyCatalog(await patchUserDropdownItem(row.id, { label: next }))
    const rest = { ...labelDraft.value }
    delete rest[row.id]
    labelDraft.value = rest
  } catch {
    notify.errorKey('admin.userDropdown.saveFail')
  }
}

async function linkCourse(
  row: unknown,
  courseId: string | number | null | undefined
): Promise<void> {
  if (!isRow(row) || !canEdit.value) return
  const next = courseId ? String(courseId) : null
  if (next === (row.course_id || null)) return
  try {
    applyCatalog(await patchUserDropdownItem(row.id, { course_id: next }))
  } catch {
    notify.errorKey('admin.userDropdown.saveFail')
  }
}

async function remove(row: unknown): Promise<void> {
  if (!isRow(row) || !canEdit.value) return
  try {
    await ElMessageBox.confirm(t('admin.userDropdown.deleteConfirm', { name: row.label }), {
      type: 'warning',
      confirmButtonText: t('admin.confirm'),
      cancelButtonText: t('admin.cancel'),
    })
  } catch {
    return
  }
  try {
    applyCatalog(await deleteUserDropdownItem(row.id))
  } catch {
    notify.errorKey('admin.userDropdown.deleteFail')
  }
}

async function preview(row: unknown): Promise<void> {
  if (!isRow(row)) return
  if (!row.course_id) {
    notify.errorKey('admin.userDropdown.previewNeedCourse')
    return
  }
  previewVisible.value = true
  previewLoading.value = true
  previewCourse.value = null
  try {
    previewCourse.value = await fetchTrainingCourse(row.course_id)
  } catch {
    previewVisible.value = false
    notify.errorKey('admin.userDropdown.previewLoadFail')
  } finally {
    previewLoading.value = false
  }
}
</script>

<template>
  <div class="admin-user-dropdown-tab">
    <p class="admin-user-dropdown-intro">
      <I18nText k="admin.userDropdown.intro" />
    </p>

    <div
      v-if="canEdit"
      class="admin-user-dropdown-add"
    >
      <el-input
        v-model="draft"
        maxlength="40"
        :placeholder="t('admin.userDropdown.namePlaceholder')"
        @keyup.enter="addItem"
      />
      <el-button
        type="primary"
        :disabled="!draft.trim() || saving"
        @click="addItem"
      >
        <I18nText k="admin.userDropdown.add" />
      </el-button>
    </div>

    <p
      v-if="loading"
      class="py-12 text-center text-gray-500"
    >
      <I18nText k="admin.loading" />
    </p>
    <p
      v-else-if="loadError"
      class="py-12 text-center text-gray-500"
    >
      <I18nText k="admin.userDropdown.loadFail" />
    </p>
    <p
      v-else-if="items.length === 0"
      class="py-12 text-center text-gray-500"
    >
      <I18nText k="admin.userDropdown.empty" />
    </p>
    <ElTable
      v-else
      :data="items"
      class="admin-swiss-table w-full"
      stripe
      size="small"
    >
      <el-table-column min-width="180">
        <template #header>
          <I18nText k="admin.userDropdown.colName" />
        </template>
        <template #default="{ row }">
          <el-input
            v-if="canEdit && isRow(row)"
            :model-value="labelOf(row)"
            maxlength="40"
            @input="onLabelInput(row, $event)"
            @change="rename(row, $event)"
          />
          <span v-else>{{ row.label }}</span>
        </template>
      </el-table-column>
      <el-table-column min-width="220">
        <template #header>
          <I18nText k="admin.userDropdown.colCourse" />
        </template>
        <template #default="{ row }">
          <el-select
            :model-value="row.course_id"
            class="w-full"
            filterable
            clearable
            :disabled="!canEdit"
            :placeholder="t('admin.userDropdown.coursePlaceholder')"
            @change="linkCourse(row, $event)"
          >
            <el-option
              v-for="course in courses"
              :key="course.id"
              :label="course.title"
              :value="course.id"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column
        width="160"
        align="right"
      >
        <template #header>
          <I18nText k="admin.actions" />
        </template>
        <template #default="{ row }">
          <el-button
            type="primary"
            link
            size="small"
            @click="preview(row)"
          >
            <I18nText k="admin.userDropdown.preview" />
          </el-button>
          <el-button
            v-if="canEdit"
            type="danger"
            link
            size="small"
            @click="remove(row)"
          >
            <I18nText k="admin.userDropdown.delete" />
          </el-button>
        </template>
      </el-table-column>
    </ElTable>

    <TrainingCourseWalkthrough
      v-model="previewVisible"
      :course="previewCourse"
      :loading="previewLoading"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-table.css"></style>

<style scoped>
.admin-user-dropdown-intro {
  margin: 0 0 1rem;
  color: #57534e;
  font-size: 0.875rem;
  line-height: 1.5;
}
.admin-user-dropdown-add {
  display: flex;
  gap: 0.5rem;
  max-width: 28rem;
  margin-bottom: 1rem;
}
</style>
