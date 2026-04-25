<script setup lang="ts">
/**
 * School dashboard — org-scoped user list, edit, unlock, delete
 */
import { computed, onMounted, ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'

import { Edit, Loading, Search, Unlock } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

const props = defineProps<{
  orgId: number
}>()

const { t } = useLanguage()
const notify = useNotifications()

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
const editUser = ref<Record<string, unknown> | null>(null)
const editForm = ref({ phone: '', name: '' })

function orgQueryString(): string {
  return new URLSearchParams({ organization_id: String(props.orgId) }).toString()
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
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

async function openEditModal(user: unknown) {
  const u = user as Record<string, unknown>
  editUser.value = u
  const uid = u.id as number
  const q = orgQueryString()
  try {
    const res = await apiRequest(`/api/auth/admin/school/users/${uid}?${q}`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.schoolUsersLoadError'))
      return
    }
    const data = (await res.json()) as { phone?: string; name?: string | null }
    editForm.value = {
      phone: data.phone || '',
      name: (data.name as string) || '',
    }
    editModalVisible.value = true
  } catch {
    notify.error(t('admin.schoolUsersLoadError'))
  }
}

async function saveUser() {
  if (!editUser.value) return
  const id = editUser.value.id as number
  const q = orgQueryString()
  try {
    const res = await apiRequest(`/api/auth/admin/school/users/${id}?${q}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: editForm.value.name,
        phone: editForm.value.phone,
      }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.schoolUsersUpdateError'))
      return
    }
    notify.success(t('notification.saved'))
    editModalVisible.value = false
    loadUsers()
  } catch {
    notify.error(t('admin.schoolUsersUpdateError'))
  }
}

async function confirmUnlock(row: unknown) {
  try {
    await ElMessageBox.confirm(t('admin.schoolUserUnlockConfirm'), t('admin.schoolUserUnlock'), {
      type: 'warning',
    })
  } catch {
    return
  }
  const id = (row as Record<string, unknown>).id as number
  const q = orgQueryString()
  try {
    const res = await apiRequest(`/api/auth/admin/school/users/${id}/unlock?${q}`, {
      method: 'PUT',
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.schoolUsersUnlockError'))
      return
    }
    const data = (await res.json()) as { message?: string }
    notify.success(data.message || t('notification.saved'))
    loadUsers()
  } catch {
    notify.error(t('admin.schoolUsersUnlockError'))
  }
}

async function confirmDeleteUser(row: unknown) {
  const o = row as Record<string, unknown>
  const name = String(o.name ?? o.phone ?? '')
  try {
    await ElMessageBox.confirm(t('admin.schoolDeleteUserConfirm', { name }), t('admin.delete'), {
      type: 'warning',
    })
  } catch {
    return
  }
  const id = o.id as number
  const q = orgQueryString()
  try {
    const res = await apiRequest(`/api/auth/admin/school/users/${id}?${q}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.schoolUsersDeleteError'))
      return
    }
    const data = (await res.json()) as { message?: string }
    notify.success(data.message || t('notification.saved'))
    loadUsers()
  } catch {
    notify.error(t('admin.schoolUsersDeleteError'))
  }
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

function userDisplayName(row: unknown): string {
  const o = row as Record<string, unknown>
  const n = o.name
  if (n != null && String(n).trim() !== '') return String(n)
  const p = o.phone
  if (p != null && String(p).trim() !== '') return String(p)
  return '-'
}

function userTokenTotal(row: unknown): number {
  const o = row as Record<string, unknown>
  const ts = o.token_stats as { total_tokens?: number } | undefined
  return ts?.total_tokens ?? 0
}

function isRowLocked(row: unknown): boolean {
  const o = row as Record<string, unknown>
  return Boolean(o.locked_until)
}

onMounted(() => {
  loadUsers()
})

watch(
  () => props.orgId,
  () => {
    pagination.value.page = 1
    loadUsers()
  }
)
</script>

<template>
  <div class="school-dashboard-users-tab pt-4">
    <el-card shadow="never">
      <template #header>
        <div class="flex items-center justify-between flex-wrap gap-4">
          <span class="font-medium">{{ t('admin.schoolUsersTitle') }}</span>
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
            <el-button
              type="primary"
              size="small"
              @click="doSearch"
            >
              {{ t('admin.search') }}
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
            min-width="120"
          >
            <template #default="{ row }">
              {{ userDisplayName(row) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="role"
            :label="t('admin.schoolUserColumnRole')"
            width="100"
          />
          <el-table-column
            :label="t('admin.tokensUsed')"
            width="100"
          >
            <template #default="{ row }">
              {{ formatNumber(userTokenTotal(row)) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="created_at"
            :label="t('admin.registrationTime')"
            width="180"
          />
          <el-table-column
            :label="t('admin.actions')"
            width="200"
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
              <el-button
                v-if="isRowLocked(row)"
                link
                type="warning"
                size="small"
                @click="confirmUnlock(row)"
              >
                <el-icon><Unlock /></el-icon>
                {{ t('admin.schoolUserUnlock') }}
              </el-button>
              <el-button
                link
                type="danger"
                size="small"
                @click="confirmDeleteUser(row)"
              >
                {{ t('admin.delete') }}
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
      </template>
    </el-card>

    <el-dialog
      v-model="editModalVisible"
      :title="`${t('common.edit')} — ${t('admin.users')}`"
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
            :placeholder="t('admin.name')"
          />
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
