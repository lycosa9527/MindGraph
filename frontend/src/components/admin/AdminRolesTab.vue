<script setup lang="ts">
/**
 * Admin Roles Tab — four platform roles with members listed per tab.
 */
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Loading, UserFilled } from '@element-plus/icons-vue'

import AdminRoleAddMemberDialog from '@/components/admin/AdminRoleAddMemberDialog.vue'
import { useLanguage } from '@/composables'
import { useAdminRoleControl } from '@/composables/admin/useAdminRoleControl'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  isRoleControlTab,
  ROLE_CONTROL_TABS,
} from '@/composables/admin/adminRoleControlNav'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useAdminPanelStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()
const { canEditTab } = useAdminAccess()
const adminPanel = useAdminPanelStore()
const { on: onAdminEvent } = useAdminEventBus('AdminRolesTab')

const {
  activeTab,
  activeRows,
  activeTabDescKey,
  addGrantingId,
  addModalVisible,
  addSearchHasRun,
  addSearchLoading,
  addSearchQuery,
  addSearchResults,
  grantActiveRole,
  isEnvRow,
  isLoading,
  loadActiveTab,
  openAddModal,
  revokeMember,
  revokingId,
  roleLabel,
  searchUsersToAdd,
  tabLabel,
} = useAdminRoleControl()

const canEdit = computed(() => canEditTab('settings'))
const showSchoolColumn = computed(() => activeTab.value === 'school_admin')
const showSuperadminColumns = computed(() => activeTab.value === 'superadmin')

function syncRoleTabToRoute(tab: typeof activeTab.value): void {
  if (route.query.subtab !== 'roles') {
    return
  }
  const current = route.query.role_tab
  if (current === tab) {
    return
  }
  void router.replace({ query: { ...route.query, role_tab: tab } })
}

watch(
  () => route.query.role_tab,
  (roleTab) => {
    if (route.query.subtab !== 'roles' || typeof roleTab !== 'string') {
      return
    }
    if (isRoleControlTab(roleTab) && roleTab !== activeTab.value) {
      activeTab.value = roleTab
    }
  }
)

watch(activeTab, (tab) => {
  syncRoleTabToRoute(tab)
  adminPanel.patchRolesToolbar({ activeRoleTab: tab })
})

watch(canEdit, (value) => {
  adminPanel.patchRolesToolbar({ canEdit: value })
})

watch(isLoading, (value) => {
  adminPanel.patchRolesToolbar({ isRefreshing: value })
})

onAdminEvent('admin:toolbar_action', (payload) => {
  if (payload.tab !== 'settings') {
    return
  }
  if (payload.action === 'roles_refresh') {
    void loadActiveTab()
  } else if (payload.action === 'roles_open_add') {
    openAddModal()
  }
})

onMounted(() => {
  const fromQuery = route.query.role_tab
  if (isRoleControlTab(fromQuery) && fromQuery !== activeTab.value) {
    activeTab.value = fromQuery
  } else {
    void loadActiveTab()
  }

  adminPanel.setRolesToolbar({
    activeRoleTab: activeTab.value,
    canEdit: canEdit.value,
    isRefreshing: isLoading.value,
  })
  syncRoleTabToRoute(activeTab.value)
})

onUnmounted(() => {
  adminPanel.clearRolesToolbar()
})
</script>

<template>
  <div class="admin-roles-tab">
    <el-tabs
      v-model="activeTab"
      class="admin-swiss-tabs"
    >
      <el-tab-pane
        v-for="roleTab in ROLE_CONTROL_TABS"
        :key="roleTab"
        :label="tabLabel(roleTab)"
        :name="roleTab"
      />
    </el-tabs>

    <p class="admin-roles-tab__desc">
      {{ t(activeTabDescKey) }}
    </p>

    <div
      v-if="isLoading"
      class="admin-roles-tab__empty"
    >
      <el-icon
        class="is-loading"
        :size="32"
      >
        <Loading />
      </el-icon>
    </div>

    <div
      v-else-if="activeRows.length === 0"
      class="admin-roles-tab__empty"
    >
      <el-icon :size="32"><UserFilled /></el-icon>
      <p class="admin-roles-tab__empty-title">{{ t('admin.noRoleMembersFound') }}</p>
      <p
        v-if="canEdit"
        class="admin-roles-tab__empty-hint"
      >
        {{ t('admin.noRoleMembersEmptyHint') }}
      </p>
    </div>

    <el-table
      v-else
      :data="activeRows"
      class="admin-swiss-table w-full"
      stripe
      size="small"
    >
      <el-table-column
        prop="phone"
        :label="t('admin.phone')"
        width="140"
      />
      <el-table-column
        prop="name"
        :label="t('admin.name')"
        width="140"
      >
        <template #default="{ row }">
          {{ row.name || row.phone || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="showSchoolColumn"
        prop="organization_name"
        :label="t('admin.schoolName')"
        min-width="160"
      >
        <template #default="{ row }">
          {{ row.organization_name || row.organization_code || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="showSuperadminColumns"
        :label="t('admin.schoolUserColumnRole')"
        width="120"
      >
        <template #default="{ row }">
          {{ roleLabel(row.role) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="created_at"
        :label="t('admin.registrationTime')"
        width="200"
      >
        <template #default="{ row }">
          {{ isEnvRow(row) ? '—' : row.created_at || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="showSuperadminColumns"
        prop="source"
        :label="t('admin.source')"
        width="120"
      >
        <template #default="{ row }">
          {{ isEnvRow(row) ? t('admin.sourceEnv') : t('admin.sourceDatabase') }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.actions')"
        width="140"
      >
        <template #default="{ row }">
          <el-button
            v-if="canEdit && !isEnvRow(row)"
            type="danger"
            link
            size="small"
            :loading="revokingId === row.id"
            @click="revokeMember(row)"
          >
            {{ t('admin.revokeRole') }}
          </el-button>
          <span
            v-else-if="isEnvRow(row)"
            class="admin-roles-tab__env-note"
          >
            {{ t('admin.envAdminsNote') }}
          </span>
          <span
            v-else
            class="admin-roles-tab__muted"
          >
            —
          </span>
        </template>
      </el-table-column>
    </el-table>

    <AdminRoleAddMemberDialog
      v-model:visible="addModalVisible"
      v-model:search-query="addSearchQuery"
      :role-tab-label="tabLabel(activeTab)"
      :results="addSearchResults"
      :loading="addSearchLoading"
      :has-run="addSearchHasRun"
      :granting-id="addGrantingId"
      :role-label-for="roleLabel"
      :show-school-in-results="showSchoolColumn"
      @search="searchUsersToAdd"
      @grant="grantActiveRole"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped src="@/styles/admin-swiss-table.css"></style>
