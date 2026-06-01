<script setup lang="ts">
import { computed } from 'vue'

import { Plus, Refresh } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'

import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage } from '@/composables'
import { useAdminPanelStore } from '@/stores'

const { t } = useLanguage()
const adminPanel = useAdminPanelStore()
const { rolesToolbar } = storeToRefs(adminPanel)
const { emit: emitAdminEvent } = useAdminEventBus('AdminRolesHeaderToolbar')

const canEdit = computed(() => rolesToolbar.value?.canEdit ?? false)
const isRefreshing = computed(() => rolesToolbar.value?.isRefreshing ?? false)

function onRefresh(): void {
  emitAdminEvent('admin:toolbar_action', { action: 'roles_refresh', tab: 'settings' })
}

function onAdd(): void {
  emitAdminEvent('admin:toolbar_action', { action: 'roles_open_add', tab: 'settings' })
}
</script>

<template>
  <div
    v-if="rolesToolbar"
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
