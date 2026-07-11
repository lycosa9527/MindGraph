<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import { Search } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'

import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage } from '@/composables'
import { useAdminOrganizations } from '@/composables/queries'
import { useAdminPanelStore } from '@/stores'
import { userRoleLabel, userRoleSelectTiers } from '@/utils/userRoleDisplay'

const { t } = useLanguage()
const adminPanel = useAdminPanelStore()
const { usersToolbar } = storeToRefs(adminPanel)
const { emit: emitAdminEvent } = useAdminEventBus('AdminUsersHeaderToolbar')
const orgsQuery = useAdminOrganizations()
const organizations = computed(() => orgsQuery.data.value ?? [])
const roleSelectTiers = computed(() => userRoleSelectTiers())

const searchQuery = computed({
  get: () => usersToolbar.value?.searchQuery ?? '',
  set: (value: string) => {
    adminPanel.patchUsersToolbar({ searchQuery: value })
  },
})

const orgFilter = computed({
  get: () => usersToolbar.value?.orgFilter ?? '',
  set: (value: number | '') => {
    adminPanel.patchUsersToolbar({ orgFilter: value })
  },
})

const roleFilter = computed({
  get: () => usersToolbar.value?.roleFilter ?? '',
  set: (value: string) => {
    adminPanel.patchUsersToolbar({ roleFilter: value || '' })
  },
})

const showSchoolFilter = computed(() => usersToolbar.value?.showSchoolFilter === true)
const showRoleFilter = computed(() => usersToolbar.value?.showRoleFilter === true)

const SCHOOL_SELECT_POPPER_CLASS = 'admin-swiss-school-select-popper'
const ROLE_SELECT_POPPER_CLASS = 'admin-swiss-role-select-popper'

onMounted(() => {
  if (showSchoolFilter.value) {
    void orgsQuery.refetch()
  }
})

watch(showSchoolFilter, (enabled) => {
  if (enabled) {
    void orgsQuery.refetch()
  }
})

function onSearch(): void {
  emitAdminEvent('admin:toolbar_action', { action: 'users_search', tab: 'users' })
}

function onReset(): void {
  emitAdminEvent('admin:toolbar_action', { action: 'users_reset_filters', tab: 'users' })
}

function onOrgFilterChange(value: number | ''): void {
  emitAdminEvent('admin:toolbar_action', {
    action: 'users_org_filter_change',
    tab: 'users',
    payload: { value },
  })
}

function onRoleFilterChange(value: string): void {
  emitAdminEvent('admin:toolbar_action', {
    action: 'users_role_filter_change',
    tab: 'users',
    payload: { value: value || '' },
  })
}
</script>

<template>
  <div
    v-if="usersToolbar"
    class="admin-swiss-toolbar admin-swiss-toolbar--header"
  >
    <el-input
      v-model="searchQuery"
      :placeholder="t('admin.search')"
      clearable
      size="small"
      class="admin-swiss-input"
      @keyup.enter="onSearch"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>
    </el-input>
    <el-select
      v-if="showSchoolFilter"
      v-model="orgFilter"
      filterable
      :placeholder="t('admin.filterBySchool')"
      clearable
      size="small"
      class="admin-swiss-select admin-swiss-select--school"
      :popper-class="SCHOOL_SELECT_POPPER_CLASS"
      @change="onOrgFilterChange"
    >
      <el-option
        :label="t('admin.allSchools')"
        value=""
      >
        <span class="admin-swiss-school-option__label">{{ t('admin.allSchools') }}</span>
      </el-option>
      <el-option
        v-for="org in organizations"
        :key="org.id"
        :label="org.name"
        :value="org.id"
      >
        <span class="admin-swiss-school-option__label">{{ org.name }}</span>
      </el-option>
    </el-select>
    <el-select
      v-if="showRoleFilter"
      v-model="roleFilter"
      filterable
      :placeholder="t('admin.filterByUserType')"
      clearable
      size="small"
      class="admin-swiss-select admin-swiss-select--role"
      :popper-class="ROLE_SELECT_POPPER_CLASS"
      @change="onRoleFilterChange"
    >
      <el-option
        :label="t('admin.allUserTypes')"
        value=""
      />
      <el-option-group
        v-for="tier in roleSelectTiers"
        :key="tier.tierLabelKey"
        :label="t(tier.tierLabelKey)"
      >
        <el-option
          v-for="role in tier.roles"
          :key="role"
          :label="userRoleLabel(t, role)"
          :value="role"
        />
      </el-option-group>
    </el-select>
    <el-button
      size="small"
      class="admin-swiss-btn"
      @click="onSearch"
    >
      {{ t('admin.search') }}
    </el-button>
    <el-button
      v-if="usersToolbar?.hasResetFilters"
      size="small"
      class="admin-swiss-btn admin-swiss-btn--ghost"
      @click="onReset"
    >
      {{ t('admin.reset') }}
    </el-button>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
