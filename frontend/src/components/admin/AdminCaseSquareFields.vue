<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useQueryClient } from '@tanstack/vue-query'
import {
  createAdminCaseSquareFieldOption,
  deleteAdminCaseSquareFieldOption,
  getAdminCaseSquareFieldOptions,
  patchAdminCaseSquareFieldOption,
  type CaseSquareFieldOptionRow,
} from '@/utils/apiClient'

const FIELD_CATEGORIES = ['subject', 'grade', 'recommended_tag'] as const
type FieldCategory = (typeof FIELD_CATEGORIES)[number]

const { t } = useLanguage()
const notify = useNotifications()
const queryClient = useQueryClient()

const activeCategory = ref<FieldCategory>('subject')
const options = ref<CaseSquareFieldOptionRow[]>([])
const isLoading = ref(false)
const loadError = ref<string | null>(null)
const isSaving = ref(false)

const newValue = ref('')
const newLabel = ref('')

const editVisible = ref(false)
const editingRow = ref<CaseSquareFieldOptionRow | null>(null)
const editLabel = ref('')
const editSortOrder = ref(0)
const editActive = ref(true)

const categoryOptions = computed(() =>
  FIELD_CATEGORIES.map((value) => ({
    value,
    label: String(t(`admin.caseSquare.fieldCategory.${value}`)),
  }))
)

const filteredOptions = computed(() =>
  options.value.filter((row) => row.category === activeCategory.value)
)

async function loadOptions(): Promise<void> {
  isLoading.value = true
  loadError.value = null
  try {
    const res = await getAdminCaseSquareFieldOptions(true)
    options.value = res.options
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Failed to load'
    options.value = []
  } finally {
    isLoading.value = false
  }
}

async function invalidateMetaCache(): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: ['caseSquareMeta'] })
}

async function createOption(): Promise<void> {
  const value = newValue.value.trim()
  if (!value) {
    notify.error(String(t('admin.caseSquare.fields.valueRequired')))
    return
  }
  isSaving.value = true
  try {
    await createAdminCaseSquareFieldOption({
      category: activeCategory.value,
      value,
      label_zh: newLabel.value.trim() || value,
    })
    newValue.value = ''
    newLabel.value = ''
    notify.success(String(t('admin.caseSquare.fields.created')))
    await loadOptions()
    await invalidateMetaCache()
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  } finally {
    isSaving.value = false
  }
}

function openEdit(row: CaseSquareFieldOptionRow): void {
  editingRow.value = row
  editLabel.value = row.label_zh
  editSortOrder.value = row.sort_order
  editActive.value = row.is_active
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  if (!editingRow.value) return
  isSaving.value = true
  try {
    await patchAdminCaseSquareFieldOption(editingRow.value.id, {
      label_zh: editLabel.value.trim() || editingRow.value.value,
      sort_order: editSortOrder.value,
      is_active: editActive.value,
    })
    notify.success(String(t('admin.caseSquare.fields.updated')))
    editVisible.value = false
    await loadOptions()
    await invalidateMetaCache()
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  } finally {
    isSaving.value = false
  }
}

async function toggleActive(row: CaseSquareFieldOptionRow): Promise<void> {
  try {
    await patchAdminCaseSquareFieldOption(row.id, { is_active: !row.is_active })
    await loadOptions()
    await invalidateMetaCache()
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function removeOption(row: CaseSquareFieldOptionRow): Promise<void> {
  try {
    await deleteAdminCaseSquareFieldOption(row.id)
    notify.success(String(t('admin.caseSquare.fields.deleted')))
    await loadOptions()
    await invalidateMetaCache()
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

onMounted(() => {
  void loadOptions()
})
</script>

<template>
  <div
    v-loading="isLoading"
    class="space-y-4"
  >
    <p class="text-sm text-gray-500">
      {{ t('admin.caseSquare.fieldsIntro') }}
    </p>

    <AdminSwissSegmented
      v-model="activeCategory"
      :options="categoryOptions"
      :aria-label="t('admin.caseSquare.fieldsCategoryAria')"
      fit
    />

    <p
      v-if="loadError"
      class="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {{ loadError }}
    </p>

    <div class="rounded-xl border border-gray-200 bg-white p-4">
      <h3 class="mb-3 text-sm font-semibold text-gray-900">
        {{ t('admin.caseSquare.fieldsAdd') }}
      </h3>
      <div class="flex flex-wrap items-end gap-3">
        <div class="min-w-[140px] flex-1">
          <label class="mb-1 block text-xs text-gray-500">{{ t('admin.caseSquare.fields.value') }}</label>
          <input
            v-model="newValue"
            type="text"
            maxlength="100"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
          />
        </div>
        <div class="min-w-[140px] flex-1">
          <label class="mb-1 block text-xs text-gray-500">{{ t('admin.caseSquare.fields.label') }}</label>
          <input
            v-model="newLabel"
            type="text"
            maxlength="100"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
          />
        </div>
        <button
          type="button"
          class="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          :disabled="isSaving"
          @click="createOption"
        >
          {{ t('admin.caseSquare.fields.add') }}
        </button>
      </div>
    </div>

    <div class="flex items-center justify-between">
      <h3 class="text-sm font-semibold text-gray-900">
        {{ t('admin.caseSquare.fieldsExisting') }}
        <span class="ml-1 text-xs font-normal text-gray-400">({{ filteredOptions.length }})</span>
      </h3>
    </div>

    <el-table
      v-if="filteredOptions.length > 0 || isLoading"
      :data="filteredOptions"
      stripe
      style="width: 100%"
    >
      <el-table-column
        prop="value"
        :label="t('admin.caseSquare.fields.value')"
        min-width="120"
      />
      <el-table-column
        prop="label_zh"
        :label="t('admin.caseSquare.fields.label')"
        min-width="120"
      />
      <el-table-column
        prop="sort_order"
        :label="t('admin.caseSquare.fields.sortOrder')"
        width="90"
      />
      <el-table-column
        :label="t('admin.caseSquare.fields.active')"
        width="100"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.is_active ? 'success' : 'info'"
            size="small"
          >
            {{ row.is_active ? t('admin.yes') : t('admin.no') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.actions')"
        width="220"
        fixed="right"
      >
        <template #default="{ row }">
          <button
            type="button"
            class="mr-3 text-sm text-gray-700 hover:text-gray-900"
            @click="openEdit(row)"
          >
            {{ t('admin.edit') }}
          </button>
          <button
            type="button"
            class="mr-3 text-sm text-gray-700 hover:text-gray-900"
            @click="toggleActive(row)"
          >
            {{ row.is_active ? t('admin.caseSquare.fields.deactivate') : t('admin.caseSquare.fields.activate') }}
          </button>
          <button
            type="button"
            class="text-sm text-red-600 hover:text-red-700"
            @click="removeOption(row)"
          >
            {{ t('admin.delete') }}
          </button>
        </template>
      </el-table-column>
    </el-table>

    <div
      v-else-if="!isLoading"
      class="rounded-xl border border-dashed border-gray-200 bg-white px-6 py-12 text-center text-sm text-gray-400"
    >
      {{ t('admin.caseSquare.fields.empty') }}
    </div>

    <el-dialog
      v-model="editVisible"
      :title="t('admin.caseSquare.fields.editTitle')"
      width="420px"
    >
      <div
        v-if="editingRow"
        class="space-y-4"
      >
        <div>
          <label class="mb-1 block text-xs text-gray-500">{{ t('admin.caseSquare.fields.value') }}</label>
          <input
            :value="editingRow.value"
            type="text"
            disabled
            class="w-full rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm text-gray-500"
          />
        </div>
        <div>
          <label class="mb-1 block text-xs text-gray-500">{{ t('admin.caseSquare.fields.label') }}</label>
          <input
            v-model="editLabel"
            type="text"
            maxlength="100"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
          />
        </div>
        <div>
          <label class="mb-1 block text-xs text-gray-500">{{ t('admin.caseSquare.fields.sortOrder') }}</label>
          <input
            v-model.number="editSortOrder"
            type="number"
            min="0"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
          />
        </div>
        <label class="flex cursor-pointer items-center gap-2 text-sm text-gray-700">
          <input
            v-model="editActive"
            type="checkbox"
          />
          {{ t('admin.caseSquare.fields.active') }}
        </label>
      </div>
      <template #footer>
        <button
          type="button"
          class="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          @click="editVisible = false"
        >
          {{ t('admin.cancel') }}
        </button>
        <button
          type="button"
          class="ml-2 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          :disabled="isSaving"
          @click="saveEdit"
        >
          {{ t('admin.save') }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>
