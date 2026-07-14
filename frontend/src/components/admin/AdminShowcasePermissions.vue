<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { useDebounceFn } from '@vueuse/core'

import {
  SHOWCASE_STAFF_PERMISSIONS,
  showcaseStaffPermissionLabelKey,
  type ShowcaseStaffPermission,
} from '@/composables/admin/adminShowcaseNav'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminUsers } from '@/composables/queries'
import {
  deleteAdminShowcaseStaffGrant,
  getAdminShowcaseStaffGrants,
  saveAdminShowcaseStaffGrant,
  type ShowcaseStaffGrantRow,
} from '@/utils/apiClient'

interface SearchUserRow {
  id: number
  phone?: string
  name?: string | null
}

const { t } = useLanguage()
const notify = useNotifications()

const grants = ref<ShowcaseStaffGrantRow[]>([])
const builtinGrants = ref<ShowcaseStaffGrantRow[]>([])
const isLoading = ref(false)
const loadError = ref<string | null>(null)
const isSaving = ref(false)

const dialogVisible = ref(false)
const editingGrant = ref<ShowcaseStaffGrantRow | null>(null)
const searchQuery = ref('')
const selectedUserId = ref<number | null>(null)
const selectedPermissions = ref<ShowcaseStaffPermission[]>([])
const grantNote = ref('')

const userSearchParams = computed(() => ({
  page: 1,
  page_size: 20,
  search: searchQuery.value.trim(),
}))
const userSearchEnabled = computed(() => searchQuery.value.trim().length >= 2)
const userSearchQuery = useAdminUsers(userSearchParams, { enabled: userSearchEnabled })

const searchResults = computed((): SearchUserRow[] => {
  const raw = userSearchQuery.data.value?.users ?? []
  const grantedIds = new Set(grants.value.map((g) => g.user_id))
  return raw
    .map((u) => ({
      id: Number(u.id),
      phone: typeof u.phone === 'string' ? u.phone : undefined,
      name: typeof u.name === 'string' ? u.name : null,
    }))
    .filter((u) => Number.isFinite(u.id) && u.id > 0)
    .filter((u) => !grantedIds.has(u.id) || u.id === editingGrant.value?.user_id)
})

const allRows = computed(() => [...builtinGrants.value, ...grants.value])

const permissionOptions = computed(() =>
  SHOWCASE_STAFF_PERMISSIONS.map((perm) => ({
    value: perm,
    label: String(t(showcaseStaffPermissionLabelKey(perm))),
  }))
)

function permLabel(perm: string): string {
  if ((SHOWCASE_STAFF_PERMISSIONS as readonly string[]).includes(perm)) {
    return String(t(showcaseStaffPermissionLabelKey(perm as ShowcaseStaffPermission)))
  }
  return perm
}

async function loadGrants(): Promise<void> {
  isLoading.value = true
  loadError.value = null
  try {
    const res = await getAdminShowcaseStaffGrants()
    grants.value = res.grants
    builtinGrants.value = res.builtin ?? []
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : 'Failed to load'
    grants.value = []
    builtinGrants.value = []
  } finally {
    isLoading.value = false
  }
}

function openCreateDialog(): void {
  editingGrant.value = null
  searchQuery.value = ''
  selectedUserId.value = null
  selectedPermissions.value = []
  grantNote.value = ''
  dialogVisible.value = true
}

function openEditDialog(row: ShowcaseStaffGrantRow): void {
  if (row.source === 'builtin' || row.editable === false) return
  editingGrant.value = row
  searchQuery.value = row.user_phone ?? row.user_name ?? String(row.user_id)
  selectedUserId.value = row.user_id
  selectedPermissions.value = row.permissions.filter((p): p is ShowcaseStaffPermission =>
    (SHOWCASE_STAFF_PERMISSIONS as readonly string[]).includes(p)
  )
  grantNote.value = row.note ?? ''
  dialogVisible.value = true
}

function togglePermission(perm: ShowcaseStaffPermission): void {
  if (selectedPermissions.value.includes(perm)) {
    selectedPermissions.value = selectedPermissions.value.filter((p) => p !== perm)
  } else {
    selectedPermissions.value = [...selectedPermissions.value, perm]
  }
}

async function saveGrant(): Promise<void> {
  const userId = editingGrant.value?.user_id ?? selectedUserId.value
  if (!userId) {
    notify.error(String(t('admin.showcase.permissions.userRequired')))
    return
  }
  if (selectedPermissions.value.length === 0) {
    notify.error(String(t('admin.showcase.permissions.permRequired')))
    return
  }
  isSaving.value = true
  try {
    await saveAdminShowcaseStaffGrant({
      user_id: userId,
      permissions: selectedPermissions.value,
      note: grantNote.value.trim() || undefined,
    })
    notify.success(String(t('admin.showcase.permissions.saved')))
    dialogVisible.value = false
    await loadGrants()
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  } finally {
    isSaving.value = false
  }
}

async function revokeGrant(row: ShowcaseStaffGrantRow): Promise<void> {
  if (row.source === 'builtin' || row.editable === false) return
  try {
    await deleteAdminShowcaseStaffGrant(row.user_id)
    notify.success(String(t('admin.showcase.permissions.revoked')))
    await loadGrants()
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

function selectUser(userId: number): void {
  selectedUserId.value = userId
}

const debouncedSearch = useDebounceFn(() => {
  if (searchQuery.value.trim().length >= 2) {
    void userSearchQuery.refetch()
  }
}, 400)

watch(searchQuery, () => {
  if (!editingGrant.value) {
    selectedUserId.value = null
  }
  debouncedSearch()
})

onMounted(() => {
  void loadGrants()
})
</script>

<template>
  <div
    v-loading="isLoading"
    class="space-y-4"
  >
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-gray-500">
        {{ t('admin.showcase.permissionsIntro') }}
      </p>
      <button
        type="button"
        class="rounded-xl bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
        @click="openCreateDialog"
      >
        {{ t('admin.showcase.permissions.add') }}
      </button>
    </div>

    <p
      v-if="loadError"
      class="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {{ loadError }}
    </p>

    <el-table
      v-if="allRows.length > 0 || isLoading"
      :data="allRows"
      stripe
      style="width: 100%"
    >
      <el-table-column
        :label="t('admin.name')"
        min-width="120"
      >
        <template #default="{ row }">
          {{ row.user_name || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.phone')"
        width="140"
      >
        <template #default="{ row }">
          {{ row.user_phone || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.organization')"
        min-width="120"
      >
        <template #default="{ row }">
          {{ row.organization || '—' }}
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.showcase.permissions.colSource')"
        width="110"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.source === 'builtin' ? 'warning' : 'info'"
            size="small"
          >
            {{
              row.source === 'builtin'
                ? t('admin.showcase.permissions.builtin')
                : t('admin.showcase.permissions.custom')
            }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.showcase.permissions.colPerms')"
        min-width="220"
      >
        <template #default="{ row }">
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="perm in row.permissions"
              :key="perm"
              size="small"
              type="info"
            >
              {{ permLabel(perm) }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column
        :label="t('admin.actions')"
        width="160"
        fixed="right"
      >
        <template #default="{ row }">
          <template v-if="row.editable !== false && row.source !== 'builtin'">
            <button
              type="button"
              class="mr-3 text-sm text-gray-700 hover:text-gray-900"
              @click="openEditDialog(row)"
            >
              {{ t('admin.edit') }}
            </button>
            <button
              type="button"
              class="text-sm text-red-600 hover:text-red-700"
              @click="revokeGrant(row)"
            >
              {{ t('admin.showcase.permissions.revoke') }}
            </button>
          </template>
          <span
            v-else
            class="text-xs text-gray-400"
          >
            {{ t('admin.showcase.permissions.builtinLocked') }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <div
      v-else-if="!isLoading"
      class="rounded-xl border border-dashed border-gray-200 bg-white px-6 py-12 text-center text-sm text-gray-400"
    >
      {{ t('admin.showcase.permissions.empty') }}
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingGrant ? t('admin.showcase.permissions.editTitle') : t('admin.showcase.permissions.addTitle')"
      width="520px"
    >
      <div class="space-y-4">
        <div v-if="!editingGrant">
          <label class="mb-1 block text-sm text-gray-700">{{ t('admin.showcase.permissions.searchUser') }}</label>
          <input
            v-model="searchQuery"
            type="search"
            :placeholder="String(t('admin.showcase.permissions.searchPlaceholder'))"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
          />
          <p
            v-if="searchQuery.trim().length >= 2 && searchResults.length === 0 && !userSearchQuery.isFetching.value"
            class="mt-2 text-xs text-gray-400"
          >
            {{ t('admin.showcase.permissions.noSearchResults') }}
          </p>
          <ul
            v-if="searchResults.length > 0"
            class="mt-2 max-h-40 overflow-y-auto rounded-lg border border-gray-100"
          >
            <li
              v-for="user in searchResults"
              :key="user.id"
            >
              <button
                type="button"
                :class="[
                  'flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-gray-50',
                  selectedUserId === user.id ? 'bg-gray-100 font-medium' : '',
                ]"
                @click="selectUser(user.id)"
              >
                <span>{{ user.name || user.phone }}</span>
                <span class="text-xs text-gray-400">{{ user.phone }}</span>
              </button>
            </li>
          </ul>
        </div>

        <div>
          <label class="mb-2 block text-sm font-medium text-gray-700">{{ t('admin.showcase.permissions.selectPerms') }}</label>
          <div class="space-y-2">
            <label
              v-for="opt in permissionOptions"
              :key="opt.value"
              class="flex cursor-pointer items-center gap-2 text-sm text-gray-700"
            >
              <input
                type="checkbox"
                :checked="selectedPermissions.includes(opt.value)"
                @change="togglePermission(opt.value)"
              />
              {{ opt.label }}
            </label>
          </div>
        </div>

        <div>
          <label class="mb-1 block text-sm text-gray-700">{{ t('admin.showcase.permissions.note') }}</label>
          <textarea
            v-model="grantNote"
            rows="2"
            maxlength="500"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400"
          />
        </div>
      </div>

      <template #footer>
        <button
          type="button"
          class="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          @click="dialogVisible = false"
        >
          {{ t('admin.cancel') }}
        </button>
        <button
          type="button"
          class="ml-2 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          :disabled="isSaving"
          @click="saveGrant"
        >
          {{ t('admin.save') }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>
