<script setup lang="ts">
/**
 * School dashboard — org-scoped user list, edit, unlock, delete
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Search } from '@element-plus/icons-vue'

import AdminSwissPagination from '@/components/admin/AdminSwissPagination.vue'
import AdminUserEditModal from '@/components/admin/AdminUserEditModal.vue'
import AdminUsersTable from '@/components/admin/AdminUsersTable.vue'

import { useAdminUsersSchoolFilterRoute } from '@/composables/admin/useAdminUsersSchoolFilterRoute'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminSchoolUsers } from '@/composables/queries'
import { useAdminPanelStore, useAuthStore } from '@/stores'

const props = withDefaults(
  defineProps<{
    orgId: number
    registerHeaderToolbar?: boolean
  }>(),
  { registerHeaderToolbar: false }
)

const authStore = useAuthStore()
const adminPanel = useAdminPanelStore()
const { t } = useLanguage()
const notify = useNotifications()
const { on: onAdminEvent } = useAdminEventBus('SchoolDashboardUsersTab')
const { orgFilter, onOrgFilterChange } = useAdminUsersSchoolFilterRoute()
const showSchoolFilterInHeader = computed(
  () => props.registerHeaderToolbar && authStore.isSuperAdmin
)

const pagination = ref({
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 0,
})
const searchQuery = ref('')

const schoolUsersParams = computed(() => ({
  page: pagination.value.page,
  page_size: pagination.value.page_size,
  search: searchQuery.value,
  organization_id: props.orgId,
}))

const schoolUsersQuery = useAdminSchoolUsers(schoolUsersParams)

const editModalVisible = ref(false)
const editUserId = ref<number | null>(null)

const isLoading = computed(() => schoolUsersQuery.isFetching.value)
const users = computed(() => (schoolUsersQuery.data.value?.users ?? []) as Record<string, unknown>[])

watch(
  () => schoolUsersQuery.data.value?.pagination,
  (nextPagination) => {
    if (nextPagination) {
      pagination.value = nextPagination
    }
  }
)

async function loadUsers() {
  try {
    await schoolUsersQuery.refetch()
  } catch {
    notify.error(t('admin.schoolUsersLoadError'))
  }
}

function openEditModal(user: unknown): void {
  const u = user as Record<string, unknown>
  const uid = u.id
  if (typeof uid !== 'number') {
    return
  }
  editUserId.value = uid
  editModalVisible.value = true
}

function doSearch() {
  pagination.value.page = 1
  loadUsers()
}

function goToPreviousUserPage() {
  pagination.value.page -= 1
  loadUsers()
}

function goToNextUserPage() {
  pagination.value.page += 1
  loadUsers()
}

const pageInfo = computed(() => {
  const p = pagination.value
  if (p.total <= 0) {
    return t('admin.listRangeEmpty')
  }
  const start = (p.page - 1) * p.page_size + 1
  const end = Math.min(p.page * p.page_size, p.total)
  return t('admin.listRange', { start, end, total: p.total })
})

function syncUsersToolbarState(): void {
  if (!props.registerHeaderToolbar) {
    return
  }
  adminPanel.setUsersToolbar({
    searchQuery: searchQuery.value,
    orgFilter: orgFilter.value,
    showSchoolFilter: showSchoolFilterInHeader.value,
    scopedOrgId: props.orgId,
    hasResetFilters: false,
  })
}

watch(searchQuery, (value) => {
  if (props.registerHeaderToolbar) {
    adminPanel.patchUsersToolbar({ searchQuery: value })
  }
})

watch(
  () => adminPanel.usersToolbar?.searchQuery,
  (value) => {
    if (!props.registerHeaderToolbar || value === undefined) {
      return
    }
    if (value !== searchQuery.value) {
      searchQuery.value = value
    }
  }
)

onAdminEvent('admin:toolbar_action', (payload) => {
  if (!props.registerHeaderToolbar || payload.tab !== 'users') {
    return
  }
  if (payload.action === 'users_search') {
    doSearch()
  } else if (payload.action === 'users_org_filter_change') {
    const raw = payload.payload?.value
    const value = raw === '' || typeof raw === 'number' ? raw : orgFilter.value
    onOrgFilterChange(value)
    pagination.value.page = 1
  }
})

onAdminEvent('admin:mutation_completed', ({ domain }) => {
  if (domain === 'school_users' || domain === 'users' || domain === 'all') {
    void loadUsers()
  }
})

onMounted(() => {
  if (props.registerHeaderToolbar) {
    syncUsersToolbarState()
  }
  loadUsers()
})

onBeforeUnmount(() => {
  if (props.registerHeaderToolbar) {
    adminPanel.clearUsersToolbar()
  }
})

watch(
  () => props.orgId,
  () => {
    pagination.value.page = 1
    loadUsers()
    if (props.registerHeaderToolbar) {
      adminPanel.patchUsersToolbar({ scopedOrgId: props.orgId })
    }
  }
)
</script>

<template>
  <div class="school-dashboard-users-tab">
    <el-card shadow="never">
      <template
        v-if="!registerHeaderToolbar"
        #header
      >
        <div class="flex items-center justify-between flex-wrap gap-4">
          <span class="font-medium">{{ t('admin.schoolUsersTitle') }}</span>
          <div class="admin-swiss-toolbar">
            <el-input
              v-model="searchQuery"
              :placeholder="t('admin.search')"
              clearable
              size="small"
              class="admin-swiss-input"
              @keyup.enter="doSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button
              size="small"
              class="admin-swiss-btn"
              @click="doSearch"
            >
              {{ t('admin.search') }}
            </el-button>
          </div>
        </div>
      </template>

      <AdminUsersTable
        :users="users"
        :is-loading="isLoading"
        :show-school-column="false"
        :link-name-and-tokens="false"
        @edit="openEditModal"
      />

      <AdminSwissPagination
        v-if="!isLoading && pagination.total_pages > 1"
        :page-info="pageInfo"
        :page="pagination.page"
        :total-pages="pagination.total_pages"
        @previous="goToPreviousUserPage"
        @next="goToNextUserPage"
      />
    </el-card>

    <AdminUserEditModal
      v-model:visible="editModalVisible"
      :user-id="editUserId"
      mode="school"
      :school-org-id="props.orgId"
      @saved="loadUsers"
      @deleted="loadUsers"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
