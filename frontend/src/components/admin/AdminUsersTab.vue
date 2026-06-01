<script setup lang="ts">
/**
 * Admin Users Tab - List, search, paginate, edit users
 * Click user row (name/tokens) to open chart + token cards modal
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'


import { useAdminUsersSchoolFilterRoute } from '@/composables/admin/useAdminUsersSchoolFilterRoute'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminUsers } from '@/composables/queries'
import { useAdminPanelStore, useAuthStore } from '@/stores'

import AdminSwissPagination from './AdminSwissPagination.vue'
import AdminTrendChartModal from './AdminTrendChartModal.vue'
import AdminUserEditModal from './AdminUserEditModal.vue'
import AdminUsersTable from './AdminUsersTable.vue'

const props = withDefaults(
  defineProps<{
    readOnly?: boolean
  }>(),
  {
    readOnly: false,
  }
)

const route = useRoute()
const authStore = useAuthStore()
const adminPanel = useAdminPanelStore()
const { on: onAdminEvent } = useAdminEventBus('AdminUsersTab')
const { orgFilter, syncOrgFilterToRoute, onOrgFilterChange: applyOrgFilterChange } =
  useAdminUsersSchoolFilterRoute()
const { t } = useLanguage()
const notify = useNotifications()

const trendModalVisible = ref(false)
const trendUser = ref<{ name: string; id?: number } | null>(null)

function openTrendModal(row: Record<string, unknown>) {
  trendUser.value = {
    name: String(row.name ?? row.phone ?? ''),
    id: row.id as number | undefined,
  }
  trendModalVisible.value = true
}

const pagination = ref({
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 0,
})
const searchQuery = ref('')

const usersQueryParams = computed(() => ({
  page: pagination.value.page,
  page_size: pagination.value.page_size,
  search: searchQuery.value,
  organization_id: orgFilter.value || undefined,
}))

const usersQuery = useAdminUsers(usersQueryParams)

const editModalVisible = ref(false)
const editUserId = ref<number | null>(null)

const isLoading = computed(() => usersQuery.isFetching.value)
const users = computed(() => (usersQuery.data.value?.users ?? []) as Record<string, unknown>[])

watch(
  () => usersQuery.data.value?.pagination,
  (nextPagination) => {
    if (nextPagination) {
      pagination.value = nextPagination
    }
  }
)

async function loadUsers() {
  try {
    await usersQuery.refetch()
  } catch {
    notify.error('Failed to load users')
  }
}

function openEditModal(user: Record<string, unknown>): void {
  const uid = user.id
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

function resetFilters() {
  searchQuery.value = ''
  orgFilter.value = ''
  pagination.value.page = 1
  if (authStore.isSuperAdmin) {
    syncOrgFilterToRoute('')
  }
  void loadUsers()
}

function onOrgFilterChange(value: number | ''): void {
  applyOrgFilterChange(value)
  pagination.value.page = 1
  void loadUsers()
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
  adminPanel.setUsersToolbar({
    searchQuery: searchQuery.value,
    orgFilter: orgFilter.value,
    showSchoolFilter: true,
    scopedOrgId: null,
    hasResetFilters: true,
  })
}

watch(searchQuery, (value) => {
  adminPanel.patchUsersToolbar({ searchQuery: value })
})

watch(orgFilter, (value) => {
  adminPanel.patchUsersToolbar({ orgFilter: value })
})

watch(
  () => adminPanel.usersToolbar?.searchQuery,
  (value) => {
    if (value !== undefined && value !== searchQuery.value) {
      searchQuery.value = value
    }
  }
)

watch(
  () => adminPanel.usersToolbar?.orgFilter,
  (value) => {
    if (value !== undefined && value !== orgFilter.value) {
      orgFilter.value = value
    }
  }
)

onAdminEvent('admin:toolbar_action', (payload) => {
  if (payload.tab !== 'users') {
    return
  }
  if (payload.action === 'users_search') {
    doSearch()
  } else if (payload.action === 'users_reset_filters') {
    resetFilters()
  } else if (payload.action === 'users_org_filter_change') {
    const raw = payload.payload?.value
    const value = raw === '' || typeof raw === 'number' ? raw : orgFilter.value
    onOrgFilterChange(value)
  }
})

onMounted(() => {
  syncUsersToolbarState()
  void loadUsers()
})

watch(
  () => route.query.organization_id,
  () => {
    if (!authStore.isSuperAdmin) {
      return
    }
    pagination.value.page = 1
    void loadUsers()
  }
)

onBeforeUnmount(() => {
  adminPanel.clearUsersToolbar()
})

</script>

<template>
  <div class="admin-users-tab">
    <el-card shadow="never">
      <AdminUsersTable
        :users="users"
        :is-loading="isLoading"
        :read-only="props.readOnly"
        show-school-column
        @edit="openEditModal"
        @open-trend="openTrendModal"
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

    <AdminTrendChartModal
      v-model:visible="trendModalVisible"
      type="user"
      :user-name="trendUser?.name"
      :user-id="trendUser?.id"
    />

    <AdminUserEditModal
      v-if="!props.readOnly"
      v-model:visible="editModalVisible"
      :user-id="editUserId"
      full-edit
      mode="global"
      @saved="loadUsers"
      @deleted="loadUsers"
    />
  </div>
</template>
