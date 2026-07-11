<script setup lang="ts">
/**
 * School modal — members/teachers with all-time token usage for one organization.
 */
import { computed, ref, watch } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import AdminSwissPagination from '@/components/admin/AdminSwissPagination.vue'
import AdminTrendChartModal from '@/components/admin/AdminTrendChartModal.vue'
import { useLanguage, useNotifications } from '@/composables'
import { fetchAdminUsers } from '@/composables/queries/adminApi'
import { schoolTierFromUserRow, userRolePillView } from '@/utils/userRoleDisplay'

const props = defineProps<{
  orgId: number | null | undefined
  canLoad: boolean
}>()

const { t } = useLanguage()
const notify = useNotifications()

const PAGE_SIZE = 15

const users = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const totalPages = ref(1)
const teacherTrendVisible = ref(false)
const teacherTrendUser = ref<{ name: string; id?: number } | null>(null)

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

const pageInfo = computed(() => {
  if (total.value <= 0) {
    return t('admin.listRangeEmpty')
  }
  const start = (page.value - 1) * PAGE_SIZE + 1
  const end = Math.min(page.value * PAGE_SIZE, total.value)
  return t('admin.listRange', { start, end, total: total.value })
})

async function loadUsers(): Promise<void> {
  const orgId = props.orgId
  if (orgId == null || orgId <= 0 || !props.canLoad) {
    return
  }
  loading.value = true
  try {
    const data = await fetchAdminUsers({
      organization_id: orgId,
      page: page.value,
      page_size: PAGE_SIZE,
    })
    users.value = data.users ?? []
    total.value = data.pagination?.total ?? 0
    totalPages.value = data.pagination?.total_pages ?? 1
  } catch {
    notify.error(t('admin.schoolTeachersTab.loadError'))
    users.value = []
    total.value = 0
    totalPages.value = 1
  } finally {
    loading.value = false
  }
}

function goToPreviousPage(): void {
  if (page.value > 1) {
    page.value -= 1
    void loadUsers()
  }
}

function goToNextPage(): void {
  if (page.value < totalPages.value) {
    page.value += 1
    void loadUsers()
  }
}

function openTeacherTrend(row: Record<string, unknown>): void {
  const rawId = row.id
  const userId = typeof rawId === 'number' ? rawId : Number(rawId)
  if (!Number.isFinite(userId) || userId <= 0) {
    notify.warning(t('admin.userTrendRequiresId'))
    return
  }
  teacherTrendUser.value = {
    name: displayName(row),
    id: userId,
  }
  teacherTrendVisible.value = true
}

watch(
  () => [props.orgId, props.canLoad] as const,
  ([orgId, canLoad]) => {
    page.value = 1
    if (orgId != null && orgId > 0 && canLoad) {
      void loadUsers()
    } else {
      users.value = []
      total.value = 0
      totalPages.value = 1
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="school-teachers-tab space-y-3">
    <div
      v-if="loading"
      class="school-modal-loading flex justify-center items-center h-48"
    >
      <el-icon
        class="is-loading"
        :size="28"
      >
        <Loading />
      </el-icon>
    </div>

    <div
      v-else-if="users.length === 0"
      class="school-modal-empty"
    >
      {{ t('admin.schoolTeachersTab.empty') }}
    </div>

    <div
      v-else
      class="overflow-x-auto"
    >
      <table class="school-modal-table">
        <thead>
          <tr class="school-modal-table__head-row">
            <th class="school-modal-table__head-cell school-modal-table__head-cell--wide">
              {{ t('admin.schoolTeachersTab.colName') }}
            </th>
            <th class="school-modal-table__head-cell">
              {{ t('admin.schoolTeachersTab.colRole') }}
            </th>
            <th class="school-modal-table__head-cell school-modal-table__head-cell--right">
              {{ t('admin.schoolTeachersTab.colTokens') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in users"
            :key="String(row.id)"
            class="school-modal-table__row school-modal-table__row--clickable"
            role="button"
            tabindex="0"
            :aria-label="t('admin.schoolTeachersTab.openUserTrend', { name: displayName(row) })"
            @click="openTeacherTrend(row)"
            @keydown.enter="openTeacherTrend(row)"
          >
            <td class="school-modal-table__cell">
              <div class="school-modal-table__name">{{ displayName(row) }}</div>
              <div
                v-if="row.phone"
                class="school-modal-table__sub"
              >
                {{ row.phone }}
              </div>
            </td>
            <td class="school-modal-table__cell whitespace-nowrap">
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
              <span v-else class="school-modal-table__sub">—</span>
            </td>
            <td class="school-modal-table__cell school-modal-table__cell--right">
              {{ formatNumber(tokenTotal(row)) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AdminSwissPagination
      v-if="users.length > 0 && totalPages > 1 && !loading"
      class="school-modal-pagination"
      :page-info="pageInfo"
      :page="page"
      :total-pages="totalPages"
      @previous="goToPreviousPage"
      @next="goToNextPage"
    />

    <AdminTrendChartModal
      v-model:visible="teacherTrendVisible"
      type="user"
      :user-name="teacherTrendUser?.name"
      :user-id="teacherTrendUser?.id"
      initial-trend-period="total"
    />
  </div>
</template>
