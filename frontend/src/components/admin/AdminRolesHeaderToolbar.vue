<script setup lang="ts">
import { computed } from 'vue'

import { Plus, Refresh } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'
import { useAdminRolesHeaderToolbarModel } from '@/composables/admin/useAdminRolesHeaderToolbar'

const { t } = useLanguage()
const toolbarState = useAdminRolesHeaderToolbarModel()
const canEdit = computed(() => toolbarState.value?.canEdit.value ?? false)
const isRefreshing = computed(() => toolbarState.value?.isRefreshing.value ?? false)

function onRefresh(): void {
  void toolbarState.value?.refresh()
}

function onAdd(): void {
  toolbarState.value?.openAddModal()
}
</script>

<template>
  <div
    v-if="toolbarState"
    class="admin-roles-header-toolbar flex items-center gap-2 shrink-0"
  >
    <el-button
      size="small"
      class="admin-swiss-btn"
      :loading="isRefreshing"
      @click="onRefresh"
    >
      <el-icon class="mr-1"><Refresh /></el-icon>
      {{ t('admin.refresh') }}
    </el-button>
    <el-button
      v-if="canEdit"
      type="primary"
      size="small"
      class="admin-swiss-btn admin-swiss-btn--primary"
      @click="onAdd"
    >
      <el-icon class="mr-1"><Plus /></el-icon>
      {{ t('admin.addRoleMember') }}
    </el-button>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
