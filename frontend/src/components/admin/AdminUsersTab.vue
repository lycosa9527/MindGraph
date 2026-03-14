<script setup lang="ts">
/**
 * Admin Users Tab - List, search, paginate, edit users
 * Click user row (name/tokens) to open chart + token cards modal
 */
import { computed, onMounted, ref, watch } from 'vue'

import { Edit, Loading, Search } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

import AdminTrendChartModal from './AdminTrendChartModal.vue'

const { t } = useLanguage()
const notify = useNotifications()

const trendModalVisible = ref(false)
const trendUser = ref<{ name: string; id?: number } | null>(null)

function openTrendModal(row: Record<string, unknown>) {
  trendUser.value = {
    name: String(row.name ?? row.phone_real ?? row.phone ?? ''),
    id: row.id as number | undefined,
  }
  trendModalVisible.value = true
}

const isLoading = ref(true)
const users = ref<Record<string, unknown>[]>([])
const organizations = ref<{ id: number; name: string; code: string }[]>([])
const pagination = ref({
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 0,
})
const searchQuery = ref('')
const orgFilter = ref<number | ''>('')

const editModalVisible = ref(false)
const editUser = ref<Record<string, unknown> | null>(null)
const editForm = ref({ phone: '', name: '', organization_id: null as number | null })

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

async function loadOrganizations() {
  const res = await apiRequest('/api/auth/admin/organizations')
  if (res.ok) {
    const data = await res.json()
    organizations.value = data.map((o: { id: number; name: string; code: string }) => ({
      id: o.id,
      name: o.name,
      code: o.code,
    }))
  }
}

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

function openEditModal(user: Record<string, unknown>) {
  editUser.value = user
  editForm.value = {
    phone: (user.phone_real as string) || (user.phone as string) || '',
    name: (user.name as string) || '',
    organization_id: (user.organization_id as number) || null,
  }
  editModalVisible.value = true
}

async function saveUser() {
  if (!editUser.value) return
  const id = editUser.value.id as number
  try {
    const res = await apiRequest(`/api/auth/admin/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(editForm.value),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to update user')
      return
    }
    notify.success(t('notification.saved'))
    editModalVisible.value = false
    loadUsers()
  } catch {
    notify.error('Failed to update user')
  }
}

function doSearch() {
  pagination.value.page = 1
  loadUsers()
}

function resetFilters() {
  searchQuery.value = ''
  orgFilter.value = ''
  pagination.value.page = 1
  loadUsers()
}

const pageInfo = computed(() => {
  const p = pagination.value
  const start = (p.page - 1) * p.page_size + 1
  const end = Math.min(p.page * p.page_size, p.total)
  return `${start}-${end} of ${p.total}`
})

onMounted(() => {
  loadOrganizations().then(loadUsers)
})

watch([orgFilter], () => {
  pagination.value.page = 1
  loadUsers()
})
</script>

<template>
  <div class="admin-users-tab pt-4">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between flex-wrap gap-4">
          <span class="font-medium">{{ t('admin.userManagement') }}</span>
          <div class="flex items-center gap-2 flex-wrap">
            <el-input
              v-model="searchQuery"
              :placeholder="t('admin.search')"
              clearable
              size="small"
              style="width: 200px"
              @keyup.enter="doSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select
              v-model="orgFilter"
              :placeholder="t('admin.filterBySchool')"
              clearable
              size="small"
              style="width: 180px"
            >
              <el-option
                :label="t('admin.allSchools')"
                value=""
              />
              <el-option
                v-for="org in organizations"
                :key="org.id"
                :label="org.name"
                :value="org.id"
              />
            </el-select>
            <el-button
              type="primary"
              size="small"
              @click="doSearch"
            >
              {{ t('admin.search') }}
            </el-button>
            <el-button
              size="small"
              @click="resetFilters"
            >
              {{ t('admin.reset') }}
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
        <el-table
          :data="users"
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
            width="120"
          >
            <template #default="{ row }">
              <span
                class="cursor-pointer hover:text-primary-500 hover:underline"
                @click="openTrendModal(row)"
              >
                {{ row.name || row.phone_real || row.phone || '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            prop="organization_name"
            :label="t('admin.organization')"
            min-width="140"
          />
          <el-table-column
            :label="t('admin.tokensUsed')"
            width="100"
          >
            <template #default="{ row }">
              <span
                class="cursor-pointer hover:text-primary-500"
                @click="openTrendModal(row)"
              >
                {{ formatNumber((row.token_stats?.total_tokens as number) ?? 0) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            prop="created_at"
            :label="t('admin.registrationTime')"
            width="180"
          />
          <el-table-column
            :label="t('admin.actions')"
            width="100"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                size="small"
                @click="openEditModal(row)"
              >
                <el-icon><Edit /></el-icon>
                {{ t('common.edit') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div
          v-if="pagination.total_pages > 1"
          class="flex justify-between items-center mt-4 pt-4 border-t border-stone-200"
        >
          <span class="text-sm text-stone-500">{{ pageInfo }}</span>
          <div class="flex gap-2">
            <el-button
              size="small"
              :disabled="pagination.page <= 1"
              @click="pagination.page--; loadUsers()"
            >
              {{ t('admin.previous') }}
            </el-button>
            <el-button
              size="small"
              :disabled="pagination.page >= pagination.total_pages"
              @click="pagination.page++; loadUsers()"
            >
              {{ t('admin.next') }}
            </el-button>
          </div>
        </div>
      </template>
    </el-card>

    <AdminTrendChartModal
      v-model:visible="trendModalVisible"
      type="user"
      :user-name="trendUser?.name"
      :user-id="trendUser?.id"
    />

    <el-dialog
      v-model="editModalVisible"
      :title="t('common.edit') + ' ' + t('admin.users')"
      width="480px"
      destroy-on-close
    >
      <el-form
        v-if="editUser"
        label-position="top"
      >
        <el-form-item :label="t('admin.phone')">
          <el-input
            v-model="editForm.phone"
            placeholder="13812345678"
            maxlength="11"
          />
        </el-form-item>
        <el-form-item :label="t('admin.name')">
          <el-input
            v-model="editForm.name"
            placeholder="Zhang Wei"
          />
        </el-form-item>
        <el-form-item :label="t('admin.organization')">
          <el-select
            v-model="editForm.organization_id"
            :placeholder="t('admin.filterBySchool')"
            clearable
            class="w-full"
          >
            <el-option
              v-for="org in organizations"
              :key="org.id"
              :label="org.name"
              :value="org.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editModalVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          @click="saveUser"
        >
          {{ t('common.save') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
