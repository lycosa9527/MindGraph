<script setup lang="ts">
/**
 * Admin Roles Tab - List admins and grant/revoke admin access
 */
import { computed, onMounted, ref } from 'vue'

import { ElMessageBox } from 'element-plus'
import { Loading, Plus, Search, UserFilled } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const { t } = useLanguage()
const notify = useNotifications()

interface AdminUser {
  id: number
  phone: string
  phone_real: string
  name: string | null
  role: string
  source: string
  created_at: string | null
}

interface CandidateUser {
  id: number
  phone: string
  phone_real?: string
  name: string | null
  role: string
}

interface EnvAdmin {
  phone: string
  name: string | null
}

const isLoading = ref(true)
const admins = ref<AdminUser[]>([])
const envAdmins = ref<EnvAdmin[]>([])

function maskPhone(phone: string): string {
  if (phone.length === 11) {
    return phone.slice(0, 3) + '****' + phone.slice(-4)
  }
  return phone
}

const dbAdminPhones = computed(() => new Set(admins.value.map((a) => a.phone_real)))
const allAdminsForTable = computed(() => {
  const dbRows = admins.value.map((a) => ({
    ...a,
    source: 'database' as const,
  }))
  const envRows = envAdmins.value
    .filter((ea) => !dbAdminPhones.value.has(ea.phone))
    .map((ea) => ({
      id: 0,
      phone: maskPhone(ea.phone),
      phone_real: ea.phone,
      name: ea.name,
      role: 'admin',
      source: 'env' as const,
      created_at: null,
    }))
  return [...dbRows, ...envRows]
})

const addModalVisible = ref(false)
const addSearchQuery = ref('')
const addSearchResults = ref<CandidateUser[]>([])
const addSearchLoading = ref(false)
const addGrantingId = ref<number | null>(null)

async function loadAdmins() {
  isLoading.value = true
  try {
    const res = await apiRequest('/api/auth/admin/admins')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to load admins')
      return
    }
    const data = await res.json()
    admins.value = data.admins ?? []
    envAdmins.value = data.env_admins ?? []
  } catch {
    notify.error('Failed to load admins')
  } finally {
    isLoading.value = false
  }
}

async function searchUsersToAdd() {
  const q = addSearchQuery.value.trim()
  if (!q || q.length < 2) {
    addSearchResults.value = []
    return
  }
  addSearchLoading.value = true
  try {
    const params = new URLSearchParams({
      page: '1',
      page_size: '20',
      search: q,
    })
    const res = await apiRequest(`/api/auth/admin/users?${params}`)
    if (!res.ok) {
      addSearchResults.value = []
      return
    }
    const data = await res.json()
    const users = (data.users ?? []) as CandidateUser[]
    const adminIds = new Set(admins.value.map((a) => a.id))
    addSearchResults.value = users.filter((u) => !adminIds.has(u.id) && u.role !== 'admin')
  } catch {
    addSearchResults.value = []
  } finally {
    addSearchLoading.value = false
  }
}

function openAddModal() {
  addModalVisible.value = true
  addSearchQuery.value = ''
  addSearchResults.value = []
}

async function grantAdmin(user: CandidateUser) {
  addGrantingId.value = user.id
  try {
    const res = await apiRequest(
      `/api/auth/admin/users/${user.id}/role?role=admin`,
      { method: 'PUT' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to grant admin')
      return
    }
    const data = await res.json()
    notify.success(data.message || t('admin.adminRoleGranted'))
    addModalVisible.value = false
    loadAdmins()
  } catch {
    notify.error('Failed to grant admin')
  } finally {
    addGrantingId.value = null
  }
}

async function revokeAdmin(admin: AdminUser) {
  try {
    const displayName = admin.name || admin.phone_real || admin.phone
    await ElMessageBox.confirm(
      `${t('admin.revokeAdminConfirm')} ${displayName}?`,
      t('admin.revokeAdmin'),
      {
        type: 'warning',
        confirmButtonText: t('admin.confirm'),
        cancelButtonText: t('admin.cancel'),
      }
    )
  } catch {
    return
  }

  try {
    const res = await apiRequest(
      `/api/auth/admin/users/${admin.id}/role?role=user`,
      { method: 'PUT' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to revoke admin')
      return
    }
    const data = await res.json()
    notify.success(data.message || t('admin.adminRoleRevoked'))
    loadAdmins()
  } catch {
    notify.error('Failed to revoke admin')
  }
}

onMounted(loadAdmins)
</script>

<template>
  <div class="admin-roles-tab pt-4">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between flex-wrap gap-4">
          <span class="font-medium">{{ t('admin.roleControl') }}</span>
          <div class="flex items-center gap-2">
            <el-button
              type="primary"
              size="small"
              @click="openAddModal"
            >
              <el-icon class="mr-1"><Plus /></el-icon>
              {{ t('admin.addAdmin') }}
            </el-button>
            <el-button
              size="small"
              @click="loadAdmins"
            >
              {{ t('admin.refresh') }}
            </el-button>
          </div>
        </div>
      </template>

      <div
        v-if="isLoading"
        class="flex justify-center py-12"
      >
        <el-icon
          class="is-loading"
          :size="32"
        >
          <Loading />
        </el-icon>
      </div>

      <template v-else>
        <p class="text-sm text-gray-500 mb-4">
          {{ t('admin.roleControlDesc') }}
        </p>

        <el-table
          :data="allAdminsForTable"
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
              {{ row.name || row.phone_real || row.phone || '-' }}
            </template>
          </el-table-column>
          <el-table-column
            prop="created_at"
            :label="t('admin.registrationTime')"
            width="200"
          >
            <template #default="{ row }">
              {{ row.source === 'database' ? (row.created_at || '—') : '—' }}
            </template>
          </el-table-column>
          <el-table-column
            prop="source"
            :label="t('admin.source')"
            width="120"
          >
            <template #default="{ row }">
              {{ row.source === 'env' ? t('admin.sourceEnv') : t('admin.sourceDatabase') }}
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.actions')"
            width="120"
          >
            <template #default="{ row }">
              <el-button
                v-if="row.source === 'database'"
                type="danger"
                link
                size="small"
                @click="revokeAdmin(row)"
              >
                {{ t('admin.revokeAdmin') }}
              </el-button>
              <span
                v-else
                class="text-xs text-gray-500"
              >
                {{ t('admin.envAdminsNote') }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-dialog
      v-model="addModalVisible"
      :title="t('admin.addAdmin')"
      width="480px"
      destroy-on-close
    >
      <div class="space-y-4">
        <el-input
          v-model="addSearchQuery"
          :placeholder="t('admin.searchUserByNameOrPhone')"
          clearable
          size="default"
          @keyup.enter="searchUsersToAdd"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
          <template #append>
            <el-button
              :loading="addSearchLoading"
              @click="searchUsersToAdd"
            >
              {{ t('admin.search') }}
            </el-button>
          </template>
        </el-input>

        <div
          v-if="addSearchResults.length === 0 && addSearchQuery.trim().length >= 2"
          class="text-center py-8 text-gray-500"
        >
          <template v-if="addSearchLoading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p class="mt-2">{{ t('admin.loading') }}</p>
          </template>
          <template v-else>
            <el-icon :size="32"><UserFilled /></el-icon>
            <p class="mt-2">{{ t('admin.noUsersFound') }}</p>
          </template>
        </div>

        <div
          v-else-if="addSearchResults.length > 0"
          class="max-h-64 overflow-y-auto space-y-2"
        >
          <div
            v-for="user in addSearchResults"
            :key="user.id"
            class="flex items-center justify-between p-3 rounded border border-gray-200 hover:bg-gray-50"
          >
            <div>
              <p class="font-medium">{{ user.name || user.phone_real || user.phone }}</p>
              <p class="text-xs text-gray-500">{{ user.phone }}</p>
            </div>
            <el-button
              type="primary"
              size="small"
              :loading="addGrantingId === user.id"
              @click="grantAdmin(user)"
            >
              {{ t('admin.grantAdmin') }}
            </el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
