<script setup lang="ts">
/**
 * Upload / restore for 系统设置 → 教学设计模板 (AdminPage header, top right).
 */
import { computed } from 'vue'

import { Upload } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'

import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage } from '@/composables'

import { useAdminPanelStore } from '@/stores'

const { t } = useLanguage()
const adminPanel = useAdminPanelStore()
const { teachingDesignToolbar } = storeToRefs(adminPanel)
const { emit: emitAdminEvent } = useAdminEventBus('AdminTeachingDesignHeaderToolbar')

const canEdit = computed(() => teachingDesignToolbar.value?.canEdit ?? false)
const canRestore = computed(() => teachingDesignToolbar.value?.canRestore ?? false)
const uploading = computed(() => teachingDesignToolbar.value?.uploading ?? false)
const restoring = computed(() => teachingDesignToolbar.value?.restoring ?? false)

function onUpload(): void {
  emitAdminEvent('admin:toolbar_action', {
    action: 'teaching_design_upload',
    tab: 'settings',
  })
}

function onRestore(): void {
  emitAdminEvent('admin:toolbar_action', {
    action: 'teaching_design_restore',
    tab: 'settings',
  })
}
</script>

<template>
  <div
    v-if="teachingDesignToolbar"
    class="admin-roles-header-toolbar flex items-center gap-2 shrink-0"
  >
    <el-button
      v-if="canRestore && canEdit"
      size="small"
      class="admin-swiss-btn"
      :loading="restoring"
      :disabled="uploading"
      @click="onRestore"
    >
      {{ t('admin.teachingDesignTemplate.restore') }}
    </el-button>
    <el-button
      v-if="canEdit"
      type="primary"
      size="small"
      class="admin-swiss-btn admin-swiss-btn--primary"
      :loading="uploading"
      :disabled="restoring"
      @click="onUpload"
    >
      <el-icon class="mr-1"><Upload /></el-icon>
      {{ t('admin.teachingDesignTemplate.upload') }}
    </el-button>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
