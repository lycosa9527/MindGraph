<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import { Search } from '@element-plus/icons-vue'

import { useAdminOrganizationsList } from '@/composables/admin/useAdminOrganizationsList'
import { useAdminUsersHeaderToolbarModel } from '@/composables/admin/useAdminUsersHeaderToolbar'
import { useLanguage } from '@/composables'

const { t } = useLanguage()
const toolbarState = useAdminUsersHeaderToolbarModel()
const { organizations, loadOrganizations } = useAdminOrganizationsList()

const searchQuery = computed({
  get: () => toolbarState.value?.searchQuery.value ?? '',
  set: (value: string) => {
    const model = toolbarState.value
    if (model) {
      model.searchQuery.value = value
    }
  },
})

const orgFilter = computed({
  get: () => toolbarState.value?.orgFilter?.value ?? '',
  set: (value: number | '') => {
    const model = toolbarState.value
    if (model?.orgFilter) {
      model.orgFilter.value = value
    }
  },
})

const showSchoolFilter = computed(() => toolbarState.value?.showSchoolFilter === true)

const SCHOOL_SELECT_POPPER_CLASS = 'admin-swiss-school-select-popper'

onMounted(() => {
  if (showSchoolFilter.value) {
    void loadOrganizations()
  }
})

watch(showSchoolFilter, (enabled) => {
  if (enabled) {
    void loadOrganizations()
  }
})

function onSearch(): void {
  toolbarState.value?.doSearch()
}

function onReset(): void {
  toolbarState.value?.resetFilters?.()
}

function onOrgFilterChange(value: number | ''): void {
  toolbarState.value?.onOrgFilterChange?.(value)
}
</script>

<template>
  <div
    v-if="toolbarState"
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
    <el-button
      size="small"
      class="admin-swiss-btn"
      @click="onSearch"
    >
      {{ t('admin.search') }}
    </el-button>
    <el-button
      v-if="toolbarState?.resetFilters"
      size="small"
      class="admin-swiss-btn admin-swiss-btn--ghost"
      @click="onReset"
    >
      {{ t('admin.reset') }}
    </el-button>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
