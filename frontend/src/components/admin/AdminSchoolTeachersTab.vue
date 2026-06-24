<script setup lang="ts">
/**
 * School modal — members/teachers with all-time token usage for one organization.
 */
import { computed, ref, watch } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { fetchAdminUsers } from '@/composables/queries/adminApi'
import { schoolTierFromUserRow, userRolePillView } from '@/utils/userRoleDisplay'

const props = defineProps<{
  orgId: number | null | undefined
  canLoad: boolean
}>()

const { t } = useLanguage()
const notify = useNotifications()

const users = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const page = ref(1)
const totalPages = ref(1)

function tokenTotal(row: Record<string, unknown>): number {
  const stats = row.token_stats as { total_tokens?: number } | undefined
  return stats?.total_tokens ?? 0
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function displayName(row: Record<string, unknown>): string {
  const name = row.name
  const phone = row.phone
  if (typeof name === 'string' && name.trim()) {
    return name
  }
  if (typeof phone === 'string' && phone.trim()) {
    return phone
  }
  return '—'
}

function rolePillForRow(row: Record<string, unknown>) {
  const role = row.role
  if (typeof role !== 'string') {
    return null
  }
  return userRolePillView(t, role, schoolTierFromUserRow(row))
}

const sortedUsers = computed(() =>
  [...users.value].sort((a, b) => tokenTotal(b) - tokenTotal(a))
)

async function loadUsers(append: boolean): Promise<void> {
  const orgId = props.orgId
  if (orgId == null || orgId <= 0 || !props.canLoad) {
    return
  }
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
    page.value = 1
  }
  try {
    const data = await fetchAdminUsers({
      organization_id: orgId,
      page: page.value,
      page_size: 100,
    })
    const batch = data.users ?? []
    if (append) {
      users.value = [...users.value, ...batch]
    } else {
      users.value = batch
    }
    totalPages.value = data.pagination?.total_pages ?? 1
  } catch {
    notify.error(t('admin.schoolTeachersTab.loadError'))
    if (!append) {
      users.value = []
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadNextPage(): void {
  if (page.value >= totalPages.value) {
    return
  }
  page.value += 1
  void loadUsers(true)
}

watch(
  () => [props.orgId, props.canLoad] as const,
  ([orgId, canLoad]) => {
    if (orgId != null && orgId > 0 && canLoad) {
      void loadUsers(false)
    } else {
      users.value = []
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="school-teachers-tab space-y-3">
    <div
      v-if="loading"
      class="flex justify-center items-center h-48"
    >
      <el-icon
        class="is-loading"
        :size="28"
      >
        <Loading />
      </el-icon>
    </div>

    <div
      v-else-if="sortedUsers.length === 0"
      class="flex justify-center items-center h-48 text-gray-500 dark:text-gray-400 text-sm"
    >
      {{ t('admin.schoolTeachersTab.empty') }}
    </div>

    <div
      v-else
      class="overflow-x-auto"
    >
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th class="py-2 pr-3 font-medium min-w-[8rem]">
              {{ t('admin.schoolTeachersTab.colName') }}
            </th>
            <th class="py-2 pr-3 font-medium whitespace-nowrap">
              {{ t('admin.schoolTeachersTab.colRole') }}
            </th>
            <th class="py-2 font-medium whitespace-nowrap text-right">
              {{ t('admin.schoolTeachersTab.colTokens') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sortedUsers"
            :key="String(row.id)"
            class="border-b border-gray-100 dark:border-gray-800 align-top"
          >
            <td class="py-2 pr-3 text-gray-800 dark:text-gray-100">
              <div class="font-medium">{{ displayName(row) }}</div>
              <div
                v-if="row.phone"
                class="text-xs text-gray-500 dark:text-gray-400 mt-0.5"
              >
                {{ row.phone }}
              </div>
            </td>
            <td class="py-2 pr-3 whitespace-nowrap">
              <span
                v-if="rolePillForRow(row)"
                class="inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-xs font-medium"
                :class="[
                  rolePillForRow(row)?.bgClass,
                  rolePillForRow(row)?.textClass,
                  rolePillForRow(row)?.borderClass,
                ]"
              >
                {{ rolePillForRow(row)?.label }}
              </span>
              <span v-else>—</span>
            </td>
            <td class="py-2 whitespace-nowrap text-right tabular-nums text-gray-700 dark:text-gray-200">
              {{ formatNumber(tokenTotal(row)) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="page < totalPages && sortedUsers.length > 0 && !loading"
      class="flex justify-center pt-2"
    >
      <el-button
        size="small"
        :loading="loadingMore"
        @click="loadNextPage"
      >
        {{ t('admin.schoolTeachersTab.loadMore') }}
      </el-button>
    </div>
  </div>
</template>
