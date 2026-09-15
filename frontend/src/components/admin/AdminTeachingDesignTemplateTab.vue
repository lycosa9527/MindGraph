<script setup lang="ts">
/**
 * 系统设置 → 教学设计模板 — catalog table + header upload.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import AdminTeachingDesignTemplateEditDialog from '@/components/admin/AdminTeachingDesignTemplateEditDialog.vue'
import AdminTeachingDesignTemplatePreviewDialog from '@/components/admin/AdminTeachingDesignTemplatePreviewDialog.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import {
  restoreTeachingDesignTemplate,
  uploadTeachingDesignTemplate,
  useAdminTeachingDesignTemplate,
  type TeachingDesignTemplateRow,
} from '@/composables/admin/teachingDesignTemplateApi'
import { useLanguage, useNotifications } from '@/composables'
import { adminKeys } from '@/composables/queries/adminKeys'
import { useAdminPanelStore } from '@/stores'

const { t } = useLanguage()
const notify = useNotifications()
const queryClient = useQueryClient()
const adminPanel = useAdminPanelStore()
const { can, isTabReadOnly } = useAdminAccess()
const { on: onAdminEvent } = useAdminEventBus('AdminTeachingDesignTemplateTab')

const fileInput = ref<HTMLInputElement | null>(null)
const templateQuery = useAdminTeachingDesignTemplate()
const editVisible = ref(false)
const editingRow = ref<TeachingDesignTemplateRow | null>(null)
const previewVisible = ref(false)
const previewRow = ref<TeachingDesignTemplateRow | null>(null)

const canEdit = computed(
  () => can('tab.settings.teaching_design') && !isTabReadOnly('settings')
)
const catalog = computed(() => templateQuery.data.value)
const templates = computed(() => catalog.value?.templates ?? [])
const loading = computed(() => templateQuery.isFetching.value)
const loadError = computed(() => templateQuery.error.value?.message ?? null)

function isTemplateRow(row: unknown): row is TeachingDesignTemplateRow {
  if (!row || typeof row !== 'object') {
    return false
  }
  const candidate = row as Record<string, unknown>
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.name === 'string' &&
    (candidate.source === 'bundled' || candidate.source === 'uploaded')
  )
}

function templateName(row: unknown): string {
  if (!isTemplateRow(row)) {
    return ''
  }
  if (row.name.trim()) {
    return row.name.trim()
  }
  if (row.source === 'bundled') {
    return t('admin.teachingDesignTemplate.optionBundled')
  }
  return row.filename || row.id
}

function sourceLabel(source: string): string {
  if (source === 'uploaded') {
    return t('admin.teachingDesignTemplate.sourceUploaded')
  }
  return t('admin.teachingDesignTemplate.sourceBundled')
}

function formatTime(value: string | null | undefined): string {
  if (!value) {
    return '—'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString()
}

function syncToolbar(): void {
  adminPanel.setTeachingDesignToolbar({
    uploading: false,
    restoring: false,
    canEdit: canEdit.value,
    canRestore: catalog.value?.can_restore ?? false,
  })
}

async function refreshCatalog(): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: adminKeys.teachingDesignTemplate() })
}

function openEdit(row: unknown): void {
  if (!isTemplateRow(row)) {
    return
  }
  editingRow.value = row
  editVisible.value = true
}

function openPreview(row: unknown): void {
  if (!isTemplateRow(row)) {
    return
  }
  previewRow.value = row
  previewVisible.value = true
}

function onEditSaved(): void {
  void refreshCatalog()
}

watch(catalog, (next) => {
  const currentId = editingRow.value?.id
  if (!currentId || !next) {
    return
  }
  editingRow.value = next.templates.find((row) => row.id === currentId) ?? editingRow.value
})

async function handleUpload(file: File): Promise<void> {
  if (!file.name.toLowerCase().endsWith('.docx')) {
    notify.error(t('admin.teachingDesignTemplate.invalidType'))
    return
  }
  adminPanel.patchTeachingDesignToolbar({ uploading: true })
  try {
    await uploadTeachingDesignTemplate(file)
    notify.success(t('admin.teachingDesignTemplate.uploadOk'))
    await refreshCatalog()
  } catch {
    notify.error(t('admin.teachingDesignTemplate.uploadFail'))
  } finally {
    adminPanel.patchTeachingDesignToolbar({ uploading: false })
  }
}

async function handleRestore(): Promise<void> {
  adminPanel.patchTeachingDesignToolbar({ restoring: true })
  try {
    await restoreTeachingDesignTemplate()
    notify.success(t('admin.teachingDesignTemplate.restoreOk'))
    await refreshCatalog()
  } catch {
    notify.error(t('admin.teachingDesignTemplate.restoreFail'))
  } finally {
    adminPanel.patchTeachingDesignToolbar({ restoring: false })
  }
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) {
    void handleUpload(file)
  }
}

onAdminEvent('admin:toolbar_action', (payload) => {
  if (payload.tab !== 'settings') {
    return
  }
  if (payload.action === 'teaching_design_upload') {
    fileInput.value?.click()
  }
  if (payload.action === 'teaching_design_restore') {
    void handleRestore()
  }
})

watch([catalog, canEdit], () => {
  if (adminPanel.teachingDesignToolbar) {
    adminPanel.patchTeachingDesignToolbar({
      canEdit: canEdit.value,
      canRestore: catalog.value?.can_restore ?? false,
    })
  }
})

onMounted(() => {
  syncToolbar()
})

onUnmounted(() => {
  adminPanel.clearTeachingDesignToolbar()
})
</script>

<template>
  <div class="admin-teaching-design-tab">
    <input
      ref="fileInput"
      type="file"
      accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      class="hidden"
      @change="onFileChange"
    />

    <p
      v-if="loading && templates.length === 0"
      class="py-12 text-center text-gray-500"
    >
      {{ t('admin.loading') }}
    </p>
    <p
      v-else-if="loadError"
      class="py-12 text-center text-gray-500"
    >
      {{ t('admin.teachingDesignTemplate.loadFail') }}
    </p>
    <ElTable
      v-else
      :data="templates"
      class="admin-swiss-table w-full"
      stripe
      size="small"
    >
      <el-table-column
        prop="index"
        :label="t('admin.teachingDesignTemplate.colIndex')"
        width="72"
      />
      <el-table-column
        :label="t('admin.teachingDesignTemplate.colName')"
        min-width="200"
      >
        <template #default="{ row }">
          <button
            type="button"
            class="admin-teaching-design-name"
            @click="openPreview(row)"
          >
            {{ templateName(row) }}
          </button>
          <span
            v-if="row.is_default"
            class="admin-teaching-design-default"
          >
            {{ t('admin.teachingDesignTemplate.defaultBadge') }}
          </span>
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.teachingDesignTemplate.colSource')"
        width="100"
      >
        <template #default="{ row }">
          {{ sourceLabel(row.source) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.teachingDesignTemplate.colUpdated')"
        width="200"
      >
        <template #default="{ row }">
          {{ formatTime(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.actions')"
        width="100"
        align="right"
      >
        <template #default="{ row }">
          <el-button
            type="primary"
            link
            size="small"
            @click="openEdit(row)"
          >
            {{ t('common.edit') }}
          </el-button>
        </template>
      </el-table-column>
    </ElTable>

    <AdminTeachingDesignTemplateEditDialog
      v-model="editVisible"
      :row="editingRow"
      :can-edit="canEdit"
      @saved="onEditSaved"
    />
    <AdminTeachingDesignTemplatePreviewDialog
      v-model="previewVisible"
      :row="previewRow"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-table.css"></style>
<style scoped>
.admin-teaching-design-name {
  padding: 0;
  border: 0;
  background: none;
  font: inherit;
  font-weight: 500;
  color: #1c1917;
  cursor: pointer;
  text-align: left;
}

.admin-teaching-design-name:hover {
  text-decoration: underline;
  text-underline-offset: 2px;
}

.admin-teaching-design-default {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  color: #78716c;
}
</style>
