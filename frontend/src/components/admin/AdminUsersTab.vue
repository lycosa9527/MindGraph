<script setup lang="ts">
/**
 * Admin Users Tab - List, search, paginate, edit users
 * Click user row (name/tokens) to open chart + token cards modal
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'


import { useAdminUsersSchoolFilterRoute } from '@/composables/admin/useAdminUsersSchoolFilterRoute'
import {
  registerAdminUsersHeaderToolbar,
  unregisterAdminUsersHeaderToolbar,
} from '@/composables/admin/useAdminUsersHeaderToolbar'
import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'
import { useAuthStore } from '@/stores'

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

const isLoading = ref(true)
const users = ref<Record<string, unknown>[]>([])
const pagination = ref({
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 0,
})
const searchQuery = ref('')

const editModalVisible = ref(false)
const editUserId = ref<number | null>(null)

async function loadUsers() {
  isLoading.value = true
  try {
    const params = new URLSearchParams({
      page: String(pagination.value.page),
      page_size: String(pagination.value.page_size),
      search: searchQuery.value,
    })
    if (orgFilter.value) params.set('organization_id', String(orgFilter.value))
    const res = await apiRequest(`/api/auth/admin/users?${params}`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to load users')
      return
    }
    const data = await res.json()
    users.value = data.users ?? []
    pagination.value = data.pagination ?? pagination.value
  } catch {
    notify.error('Failed to load users')
  } finally {
    isLoading.value = false
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

onMounted(() => {
  registerAdminUsersHeaderToolbar({
    searchQuery,
    orgFilter,
    showSchoolFilter: true,
    doSearch,
    resetFilters,
    onOrgFilterChange,
  })
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
  unregisterAdminUsersHeaderToolbar()
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
