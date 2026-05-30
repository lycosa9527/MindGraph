<script setup lang="ts">
/**
 * School dashboard — org-scoped user list, edit, unlock, delete
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Search } from '@element-plus/icons-vue'

import AdminUserEditModal from '@/components/admin/AdminUserEditModal.vue'
import AdminUsersTable from '@/components/admin/AdminUsersTable.vue'

import { useAdminUsersSchoolFilterRoute } from '@/composables/admin/useAdminUsersSchoolFilterRoute'
import {
  registerAdminUsersHeaderToolbar,
  unregisterAdminUsersHeaderToolbar,
} from '@/composables/admin/useAdminUsersHeaderToolbar'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

const props = withDefaults(
  defineProps<{
    orgId: number
    registerHeaderToolbar?: boolean
  }>(),
  { registerHeaderToolbar: false }
)

const authStore = useAuthStore()
const { t } = useLanguage()
const notify = useNotifications()
const { orgFilter, onOrgFilterChange } = useAdminUsersSchoolFilterRoute()
const showSchoolFilterInHeader = computed(
  () => props.registerHeaderToolbar && authStore.isSuperAdmin
)

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

function orgQueryString(): string {
  return new URLSearchParams({ organization_id: String(props.orgId) }).toString()
}

async function loadUsers() {
  isLoading.value = true
  try {
    const params = new URLSearchParams({
      page: String(pagination.value.page),
      page_size: String(pagination.value.page_size),
      search: searchQuery.value,
      organization_id: String(props.orgId),
    })
    const res = await apiRequest(`/api/auth/admin/school/users?${params}`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.schoolUsersLoadError'))
      return
    }
    const data = await res.json()
    users.value = data.users ?? []
    pagination.value = data.pagination ?? pagination.value
  } catch {
    notify.error(t('admin.schoolUsersLoadError'))
  } finally {
    isLoading.value = false
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

const scopedOrgId = computed(() => props.orgId)

onMounted(() => {
  if (props.registerHeaderToolbar) {
    registerAdminUsersHeaderToolbar({
      searchQuery,
      scopedOrgId,
      orgFilter: showSchoolFilterInHeader.value ? orgFilter : undefined,
      showSchoolFilter: showSchoolFilterInHeader.value,
      doSearch,
      onOrgFilterChange: showSchoolFilterInHeader.value
        ? (value) => {
            onOrgFilterChange(value)
            pagination.value.page = 1
          }
        : undefined,
    })
  }
  loadUsers()
})

onBeforeUnmount(() => {
  if (props.registerHeaderToolbar) {
    unregisterAdminUsersHeaderToolbar()
  }
})

watch(
  () => props.orgId,
  () => {
    pagination.value.page = 1
    loadUsers()
  }
)

function reloadUsers(): void {
  void loadUsers()
}

defineExpose({
  reloadUsers,
})
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

      <div
        v-if="!isLoading && pagination.total_pages > 1"
        class="flex justify-between items-center mt-4 pt-4 border-t border-stone-200"
      >
        <span class="text-sm text-stone-500">{{ pageInfo }}</span>
        <div class="flex gap-2">
          <el-button
            size="small"
            :disabled="pagination.page <= 1"
            @click="goToPreviousUserPage"
          >
            {{ t('admin.previous') }}
          </el-button>
          <el-button
            size="small"
            :disabled="pagination.page >= pagination.total_pages"
            @click="goToNextUserPage"
          >
            {{ t('admin.next') }}
          </el-button>
        </div>
      </div>
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
