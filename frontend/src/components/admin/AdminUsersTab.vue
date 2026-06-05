<script setup lang="ts">
/**
 * Admin Users Tab - List, search, paginate, edit users
 * Click user row (name/tokens) to open chart + token cards modal
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useAdminUsersSchoolFilterRoute } from '@/composables/admin/useAdminUsersSchoolFilterRoute'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminUsers } from '@/composables/queries'
import type { AdminUsersQuery } from '@/composables/queries/adminApi'
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
  const rawId = row.id
  const userId = typeof rawId === 'number' ? rawId : Number(rawId)
  if (!Number.isFinite(userId) || userId <= 0) {
    notify.warning(t('admin.userTrendRequiresId'))
    return
  }
  trendUser.value = {
    name: String(row.name ?? row.phone ?? ''),
    id: userId,
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

function buildUsersQueryParams(): AdminUsersQuery {
  const params: AdminUsersQuery = {
    page: pagination.value.page,
    page_size: pagination.value.page_size,
    search: searchQuery.value,
  }
  if (orgFilter.value !== '') {
    params.organization_id = orgFilter.value
  }
  return params
}

const usersQueryParams = computed(() => buildUsersQueryParams())

const usersQuery = useAdminUsers(usersQueryParams)

const editModalVisible = ref(false)
const editUserId = ref<number | null>(null)

const isLoading = computed(() => usersQuery.isFetching.value)
const users = computed(() => (usersQuery.data.value?.users ?? []) as Record<string, unknown>[])

const apiPagination = computed(() => usersQuery.data.value?.pagination)

const showPaginationBar = computed(
  () => !isLoading.value && usersQuery.data.value != null
)

function resetPaginationMeta(): void {
  pagination.value.total = 0
  pagination.value.total_pages = 0
}

watch(
  () => usersQuery.data.value?.pagination,
  (nextPagination) => {
    if (!nextPagination) {
      return
    }
    if (nextPagination.page !== pagination.value.page) {
      return
    }
    pagination.value.total = nextPagination.total
    pagination.value.total_pages = nextPagination.total_pages
    pagination.value.page_size = nextPagination.page_size
  }
)

watch(orgFilter, (value, oldValue) => {
  adminPanel.patchUsersToolbar({ orgFilter: value })
  if (value === oldValue) {
    return
  }
  pagination.value.page = 1
  resetPaginationMeta()
})

async function loadUsers() {
  try {
    await usersQuery.refetch()
  } catch {
    notify.error(t('admin.usersLoadError'))
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
  resetPaginationMeta()
  void loadUsers()
}

function resetFilters() {
  searchQuery.value = ''
  orgFilter.value = ''
  if (authStore.isSuperAdmin) {
    syncOrgFilterToRoute('')
  }
}

function onOrgFilterChange(value: number | ''): void {
  applyOrgFilterChange(value)
}

function goToPreviousUserPage() {
  if (pagination.value.page > 1) {
    pagination.value.page -= 1
  }
}

function goToNextUserPage() {
  const totalPages = apiPagination.value?.total_pages ?? pagination.value.total_pages
  if (pagination.value.page < totalPages) {
    pagination.value.page += 1
  }
}

const pageInfo = computed(() => {
  const meta = apiPagination.value ?? pagination.value
  if (meta.total <= 0) {
    return t('admin.listRangeEmpty')
  }
  const page = pagination.value.page
  const pageSize = meta.page_size
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, meta.total)
  return t('admin.listRange', { start, end, total: meta.total })
})

const paginationPage = computed(() => pagination.value.page)
const paginationTotalPages = computed(
  () => apiPagination.value?.total_pages ?? pagination.value.total_pages
)

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
})

onBeforeUnmount(() => {
  adminPanel.clearUsersToolbar()
})

</script>

<template>
  <div class="admin-users-tab">
    <el-card
      shadow="never"
      class="admin-users-card"
    >
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
        {{ t('admin.usersTokensAllTimeHint') }}
      </p>
      <AdminUsersTable
        :users="users"
        :is-loading="isLoading"
        :read-only="props.readOnly"
        show-school-column
        @edit="openEditModal"
        @open-trend="openTrendModal"
      />

      <template
        v-if="showPaginationBar"
        #footer
      >
        <AdminSwissPagination
          :page-info="pageInfo"
          :page="paginationPage"
          :total-pages="paginationTotalPages"
          @previous="goToPreviousUserPage"
          @next="goToNextUserPage"
        />
      </template>
    </el-card>

    <AdminTrendChartModal
      v-model:visible="trendModalVisible"
      type="user"
      :user-name="trendUser?.name"
      :user-id="trendUser?.id"
      initial-trend-period="total"
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

<style scoped src="@/styles/admin-swiss-controls.css"></style>
