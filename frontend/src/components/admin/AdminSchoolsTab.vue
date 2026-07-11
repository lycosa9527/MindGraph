<script setup lang="ts">
/**
 * Admin Schools Tab - List organizations (Swiss panel)
 * Click school row to open chart + token cards modal
 */
import { computed, ref } from 'vue'

import { Edit, Loading } from '@element-plus/icons-vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage, useNotifications } from '@/composables'
import {
  resolveSchoolMindmateAgentName,
  resolveSchoolMindmateAvatarUrl,
} from '@/composables/mindmate/useMindMateBranding'
import '@/styles/admin-schools-swiss.css'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useAdminOrganizations } from '@/composables/queries'
import { formatBeijingDate } from '@/utils/formatBeijingDateTime'
import { isOrgPrivatized } from '@/utils/orgPrivatization'

import AdminSchoolCreateDialog from './AdminSchoolCreateDialog.vue'
import AdminSchoolShareDialog from './AdminSchoolShareDialog.vue'
import AdminTrendChartModal from './AdminTrendChartModal.vue'

const SWISS_FILTER_POPPER = 'admin-swiss-school-filter-popper'

type PrivatizedFilterValue = 'yes' | 'no' | ''
type ColumnSortOrder = 'none' | 'asc' | 'desc'

const props = withDefaults(
  defineProps<{
    readOnly?: boolean
  }>(),
  {
    readOnly: false,
  }
)

const { t, isZh } = useLanguage()
const notify = useNotifications()
const { can } = useAdminAccess()
const { on: onAdminEvent } = useAdminEventBus('AdminSchoolsTab')

const dateLocale = computed(() => (isZh.value ? 'zh-CN' : 'en-US'))

const canEditOrganizations = computed(() => can('tab.organizations.edit'))
/** Experts (invited-org scope, no global): usage / teachers / activity only. */
const schoolDialogMode = computed<'manage' | 'insights'>(() =>
  can('scope.invited_orgs') && !can('scope.global') ? 'insights' : 'manage'
)
const canCreateSchool = computed(
  () =>
    (can('tab.invites.edit') || can('tab.organizations.edit')) &&
    (can('scope.global') || can('scope.invited_orgs'))
)

const organizationsQuery = useAdminOrganizations()

const isLoading = computed(() => organizationsQuery.isFetching.value)
const schools = computed(
  () => (organizationsQuery.data.value ?? []) as unknown as Record<string, unknown>[]
)
const createModalVisible = ref(false)
const shareModalVisible = ref(false)
const shareInvitationCode = ref('')
const shareOrganizationName = ref('')

const orgTableEmptyText = computed(() => {
  if (can('scope.invited_orgs') && !can('scope.global')) {
    return t('admin.inviteOrgsEmpty')
  }
  return t('admin.noData')
})
const privatizedFilter = ref<PrivatizedFilterValue>('')
const tokenSortOrder = ref<ColumnSortOrder>('none')
const expiresAtSortOrder = ref<ColumnSortOrder>('none')
const userCountSortOrder = ref<ColumnSortOrder>('none')
const managerCountSortOrder = ref<ColumnSortOrder>('none')

const columnSortOrders = [
  tokenSortOrder,
  expiresAtSortOrder,
  userCountSortOrder,
  managerCountSortOrder,
] as const

const privatizedFilterOptions = computed(() => [
  { value: '' as const, label: t('common.all') as string },
  { value: 'yes' as const, label: t('admin.orgPrivateDifyYes') as string },
  { value: 'no' as const, label: t('admin.orgPrivateDifyNo') as string },
])

function tokenTotal(row: Record<string, unknown>): number {
  const stats = row.token_stats as { total_tokens?: number } | undefined
  return stats?.total_tokens ?? 0
}

function userCountTotal(row: Record<string, unknown>): number {
  const count = row.user_count
  return typeof count === 'number' ? count : 0
}

function managerCountTotal(row: Record<string, unknown>): number {
  const count = row.manager_count
  return typeof count === 'number' ? count : 0
}

function expiresAtDatePart(iso: string | null | undefined): string | null {
  if (!iso) {
    return null
  }
  const match = iso.match(/^(\d{4}-\d{2}-\d{2})/)
  return match ? match[1] : null
}

function expiresAtSortKey(row: Record<string, unknown>): number | null {
  const datePart = expiresAtDatePart(row.expires_at as string | null | undefined)
  if (!datePart) {
    return null
  }
  return new Date(`${datePart}T00:00:00+08:00`).getTime()
}

function expiresAtLabel(row: Record<string, unknown>): string {
  const datePart = expiresAtDatePart(row.expires_at as string | null | undefined)
  if (!datePart) {
    return t('admin.noExpiration') as string
  }
  return formatBeijingDate(datePart, dateLocale.value)
}

function compareExpiresAt(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
  ascending: boolean
): number {
  const left = expiresAtSortKey(a)
  const right = expiresAtSortKey(b)
  if (left == null && right == null) {
    return 0
  }
  if (left == null) {
    return 1
  }
  if (right == null) {
    return -1
  }
  return ascending ? left - right : right - left
}

function sortTriangle(order: Exclude<ColumnSortOrder, 'none'>): string {
  return order === 'asc' ? '▲' : '▼'
}

function sortAriaValue(order: ColumnSortOrder): 'none' | 'ascending' | 'descending' {
  if (order === 'asc') {
    return 'ascending'
  }
  if (order === 'desc') {
    return 'descending'
  }
  return 'none'
}

const tokenSortAriaSort = computed(() => sortAriaValue(tokenSortOrder.value))
const expiresAtSortAriaSort = computed(() => sortAriaValue(expiresAtSortOrder.value))
const userCountSortAriaSort = computed(() => sortAriaValue(userCountSortOrder.value))
const managerCountSortAriaSort = computed(() => sortAriaValue(managerCountSortOrder.value))

const displayedSchools = computed(() => {
  let list = [...schools.value]
  if (privatizedFilter.value === 'yes') {
    list = list.filter((row) => isOrgPrivatized(row))
  } else if (privatizedFilter.value === 'no') {
    list = list.filter((row) => !isOrgPrivatized(row))
  }
  if (tokenSortOrder.value === 'asc') {
    list.sort((a, b) => tokenTotal(a) - tokenTotal(b))
  } else if (tokenSortOrder.value === 'desc') {
    list.sort((a, b) => tokenTotal(b) - tokenTotal(a))
  } else if (expiresAtSortOrder.value === 'asc') {
    list.sort((a, b) => compareExpiresAt(a, b, true))
  } else if (expiresAtSortOrder.value === 'desc') {
    list.sort((a, b) => compareExpiresAt(a, b, false))
  } else if (userCountSortOrder.value === 'asc') {
    list.sort((a, b) => userCountTotal(a) - userCountTotal(b))
  } else if (userCountSortOrder.value === 'desc') {
    list.sort((a, b) => userCountTotal(b) - userCountTotal(a))
  } else if (managerCountSortOrder.value === 'asc') {
    list.sort((a, b) => managerCountTotal(a) - managerCountTotal(b))
  } else if (managerCountSortOrder.value === 'desc') {
    list.sort((a, b) => managerCountTotal(b) - managerCountTotal(a))
  }
  return list
})

function cycleColumnSort(active: (typeof columnSortOrders)[number]): void {
  if (active.value === 'none') {
    active.value = 'desc'
    columnSortOrders.forEach((order) => {
      if (order !== active) {
        order.value = 'none'
      }
    })
    return
  }
  if (active.value === 'desc') {
    active.value = 'asc'
    return
  }
  active.value = 'none'
}

function setPrivatizedFilter(value: PrivatizedFilterValue): void {
  privatizedFilter.value = value
}

function cycleTokenSort(): void {
  cycleColumnSort(tokenSortOrder)
}

function cycleExpiresAtSort(): void {
  cycleColumnSort(expiresAtSortOrder)
}

function cycleUserCountSort(): void {
  cycleColumnSort(userCountSortOrder)
}

function cycleManagerCountSort(): void {
  cycleColumnSort(managerCountSortOrder)
}
const trendModalVisible = ref(false)
const trendOrg = ref<{
  name: string
  id?: number
  display_name?: string
  is_active?: boolean
  user_count?: number
  expires_at?: string | null
  school_tier?: string | null
  extra_member_seats?: number
  dify_api_base_url?: string | null
  dify_api_key_masked?: string | null
  dify_api_base_url_2?: string | null
  dify_api_key_2_masked?: string | null
  dify_active_server?: number
  dify_failover_enabled?: boolean
  dify_timeout_seconds?: number
  dingtalk_ai_card_streaming_max_chars?: number
  show_chain_of_thought?: boolean
  mindmate_agent_name?: string | null
  mindmate_agent_avatar_url?: string | null
  initial_tab?: 'usage' | 'teachers' | 'activity' | 'general'
  initial_trend_period?: 'today' | 'week' | 'month' | 'total'
} | null>(null)

function agentDisplayName(row: Record<string, unknown>): string {
  const customName = resolveSchoolMindmateAgentName(
    row.mindmate_agent_name as string | null | undefined
  )
  return customName ?? (t('sidebar.mindMate') as string)
}

function agentAvatarSrc(row: Record<string, unknown>): string {
  return (
    resolveSchoolMindmateAvatarUrl(row.mindmate_agent_avatar_url as string | null | undefined) ??
    mindmateAvatarMd
  )
}

function onAgentAvatarError(event: Event) {
  const img = event.target as HTMLImageElement | null
  if (img && img.src !== mindmateAvatarMd) {
    img.src = mindmateAvatarMd
  }
}

function orgShowChainOfThought(row: Record<string, unknown>): boolean {
  return Boolean(
    row.show_chain_of_thought_oto ||
      row.show_chain_of_thought_internal_group ||
      row.show_chain_of_thought_cross_org_group
  )
}

function openTrendModal(
  row: Record<string, unknown>,
  initialTab: 'usage' | 'teachers' | 'activity' | 'general' = 'usage',
  initialTrendPeriod: 'today' | 'week' | 'month' | 'total' = 'week'
) {
  trendOrg.value = {
    name: String(row.name ?? ''),
    id: row.id as number | undefined,
    display_name: row.display_name as string | undefined,
    is_active: row.is_active as boolean | undefined,
    user_count: (row.user_count as number) ?? 0,
    expires_at: row.expires_at as string | null | undefined,
    school_tier: row.school_tier as string | null | undefined,
    extra_member_seats: (row.extra_member_seats as number | undefined) ?? 0,
    dify_api_base_url: row.dify_api_base_url as string | null | undefined,
    dify_api_key_masked: row.dify_api_key_masked as string | null | undefined,
    dify_api_base_url_2: row.dify_api_base_url_2 as string | null | undefined,
    dify_api_key_2_masked: row.dify_api_key_2_masked as string | null | undefined,
    dify_active_server: (row.dify_active_server as number | undefined) ?? 1,
    dify_failover_enabled: (row.dify_failover_enabled as boolean | undefined) ?? true,
    dify_timeout_seconds: (row.dify_timeout_seconds as number | undefined) ?? 300,
    dingtalk_ai_card_streaming_max_chars:
      (row.dingtalk_ai_card_streaming_max_chars as number | undefined) ?? 6500,
    show_chain_of_thought: orgShowChainOfThought(row),
    mindmate_agent_name: row.mindmate_agent_name as string | null | undefined,
    mindmate_agent_avatar_url: row.mindmate_agent_avatar_url as string | null | undefined,
    initial_tab: initialTab,
    initial_trend_period: initialTrendPeriod,
  }
  trendModalVisible.value = true
}

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function syncTrendOrgFromSchools() {
  const trendId = trendOrg.value?.id
  const currentTrend = trendOrg.value
  if (trendId == null || !currentTrend) {
    return
  }
  const updated = schools.value.find((s: Record<string, unknown>) => s.id === trendId)
  if (updated) {
    trendOrg.value = {
      ...currentTrend,
      name: String(updated.name ?? currentTrend.name),
      display_name: updated.display_name as string | undefined,
      is_active: updated.is_active as boolean | undefined,
      user_count: (updated.user_count as number) ?? 0,
      expires_at: updated.expires_at as string | null | undefined,
      school_tier: updated.school_tier as string | null | undefined,
      extra_member_seats: (updated.extra_member_seats as number | undefined) ?? 0,
      dify_api_base_url: updated.dify_api_base_url as string | null | undefined,
      dify_api_key_masked: updated.dify_api_key_masked as string | null | undefined,
      dify_api_base_url_2: updated.dify_api_base_url_2 as string | null | undefined,
      dify_api_key_2_masked: updated.dify_api_key_2_masked as string | null | undefined,
      dify_active_server: (updated.dify_active_server as number | undefined) ?? 1,
      dify_failover_enabled: (updated.dify_failover_enabled as boolean | undefined) ?? true,
      dify_timeout_seconds: (updated.dify_timeout_seconds as number | undefined) ?? 300,
      dingtalk_ai_card_streaming_max_chars:
        (updated.dingtalk_ai_card_streaming_max_chars as number | undefined) ?? 6500,
      show_chain_of_thought: orgShowChainOfThought(updated),
      mindmate_agent_name: updated.mindmate_agent_name as string | null | undefined,
      mindmate_agent_avatar_url: updated.mindmate_agent_avatar_url as string | null | undefined,
      initial_tab: currentTrend.initial_tab,
      initial_trend_period: currentTrend.initial_trend_period,
    }
  }
}

async function loadSchools(options?: { silent?: boolean }): Promise<void> {
  try {
    await organizationsQuery.refetch()
    syncTrendOrgFromSchools()
  } catch {
    notify.error(t('admin.schoolsLoadError'))
  }
}

function openCreateModal(): void {
  createModalVisible.value = true
}

function openShareModalWithCode(code: string, orgName = ''): void {
  shareInvitationCode.value = code
  shareOrganizationName.value = orgName
  shareModalVisible.value = true
}

function onSchoolCreated(payload: { invitation_code?: string; name?: string }): void {
  void loadSchools({ silent: true })
  if (payload.invitation_code) {
    openShareModalWithCode(payload.invitation_code, payload.name ?? '')
  }
}

onAdminEvent('admin:toolbar_action', (payload) => {
  if (payload.action === 'open_create_school' && payload.tab === 'organizations') {
    if (canCreateSchool.value) {
      openCreateModal()
    }
  }
})

onAdminEvent('admin:refresh_requested', ({ domain }) => {
  if (domain === 'organizations' || domain === 'all') {
    void loadSchools({ silent: true })
  }
})
</script>

<template>
  <div class="admin-schools-tab">
    <el-card
      shadow="never"
      class="admin-schools-card"
    >
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

      <el-table
        v-else
        :data="displayedSchools"
        row-key="id"
        class="admin-schools-table w-full"
        :empty-text="orgTableEmptyText"
        stripe
        size="small"
      >
        <el-table-column
          prop="name"
          :label="t('admin.organizationName')"
          min-width="120"
          show-overflow-tooltip
          class-name="admin-schools-col-text"
        >
          <template #default="{ row }">
            <button
              type="button"
              class="admin-schools-link text-left max-w-full truncate"
              @click="openTrendModal(row, 'usage')"
            >
              {{ row.name }}
            </button>
          </template>
        </el-table-column>
        <el-table-column
          column-key="is_privatized"
          min-width="96"
          align="center"
          header-align="center"
        >
          <template #header>
            <el-dropdown
              trigger="click"
              :popper-class="SWISS_FILTER_POPPER"
              @command="setPrivatizedFilter"
            >
              <button
                type="button"
                class="admin-schools-col-header-trigger"
                :class="{ 'admin-schools-col-header-trigger--active': privatizedFilter !== '' }"
              >
                {{ t('admin.orgPrivateDify') }}
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="opt in privatizedFilterOptions"
                    :key="opt.value || 'all'"
                    :command="opt.value"
                    :class="{ 'is-selected': privatizedFilter === opt.value }"
                  >
                    {{ opt.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template #default="{ row }">
            <span
              class="admin-schools-private"
              :class="
                isOrgPrivatized(row)
                  ? 'admin-schools-private--yes'
                  : 'admin-schools-private--no'
              "
            >
              {{
                isOrgPrivatized(row)
                  ? t('admin.orgPrivateDifyYes')
                  : t('admin.orgPrivateDifyNo')
              }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          prop="mindmate_agent_name"
          :label="t('admin.schoolMindmateAgentName')"
          min-width="112"
          align="center"
          header-align="center"
          show-overflow-tooltip
          class-name="admin-schools-col-text"
        >
          <template #default="{ row }">
            <span class="text-stone-700">{{ agentDisplayName(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.orgAgentAvatar')"
          min-width="64"
          align="center"
          header-align="center"
        >
          <template #default="{ row }">
            <img
              :src="agentAvatarSrc(row)"
              :alt="agentDisplayName(row)"
              class="admin-schools-agent-avatar"
              width="32"
              height="32"
              @error="onAgentAvatarError"
            />
          </template>
        </el-table-column>
        <el-table-column
          min-width="108"
          align="center"
          header-align="center"
        >
          <template #header>
            <button
              type="button"
              class="admin-schools-col-header-trigger admin-schools-sort-header"
              :class="{ 'admin-schools-col-header-trigger--active': tokenSortOrder !== 'none' }"
              :aria-sort="tokenSortAriaSort"
              @click="cycleTokenSort"
            >
              <span>{{ t('admin.tokensUsedAllTime') }}</span>
              <span
                v-if="tokenSortOrder !== 'none'"
                class="admin-schools-sort-header__dir"
                aria-hidden="true"
              >
                {{ sortTriangle(tokenSortOrder) }}
              </span>
            </button>
          </template>
          <template #default="{ row }">
            <button
              type="button"
              class="admin-schools-link tabular-nums"
              @click="openTrendModal(row, 'usage', 'total')"
            >
              {{ formatNumber(tokenTotal(row)) }}
            </button>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.status')"
          min-width="80"
          align="center"
          header-align="center"
        >
          <template #default="{ row }">
            <span
              class="admin-schools-status"
              :class="row.is_active ? 'admin-schools-status--on' : 'admin-schools-status--off'"
            >
              {{ row.is_active ? t('admin.enabled') : t('admin.disabled') }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          min-width="108"
          align="center"
          header-align="center"
        >
          <template #header>
            <button
              type="button"
              class="admin-schools-col-header-trigger admin-schools-sort-header"
              :class="{
                'admin-schools-col-header-trigger--active': expiresAtSortOrder !== 'none',
              }"
              :aria-sort="expiresAtSortAriaSort"
              @click="cycleExpiresAtSort"
            >
              <span>{{ t('admin.expirationDate') }}</span>
              <span
                v-if="expiresAtSortOrder !== 'none'"
                class="admin-schools-sort-header__dir"
                aria-hidden="true"
              >
                {{ sortTriangle(expiresAtSortOrder) }}
              </span>
            </button>
          </template>
          <template #default="{ row }">
            <span
              class="tabular-nums"
              :class="
                expiresAtDatePart(row.expires_at as string | null | undefined)
                  ? 'text-stone-700'
                  : 'text-stone-400'
              "
            >
              {{ expiresAtLabel(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          min-width="72"
          align="center"
          header-align="center"
        >
          <template #header>
            <button
              type="button"
              class="admin-schools-col-header-trigger admin-schools-sort-header"
              :class="{ 'admin-schools-col-header-trigger--active': userCountSortOrder !== 'none' }"
              :aria-sort="userCountSortAriaSort"
              @click="cycleUserCountSort"
            >
              <span>{{ t('admin.usersCount') }}</span>
              <span
                v-if="userCountSortOrder !== 'none'"
                class="admin-schools-sort-header__dir"
                aria-hidden="true"
              >
                {{ sortTriangle(userCountSortOrder) }}
              </span>
            </button>
          </template>
          <template #default="{ row }">
            <span class="tabular-nums text-stone-700">{{ userCountTotal(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          min-width="80"
          align="center"
          header-align="center"
        >
          <template #header>
            <button
              type="button"
              class="admin-schools-col-header-trigger admin-schools-sort-header"
              :class="{
                'admin-schools-col-header-trigger--active': managerCountSortOrder !== 'none',
              }"
              :aria-sort="managerCountSortAriaSort"
              @click="cycleManagerCountSort"
            >
              <span>{{ t('admin.managerCount') }}</span>
              <span
                v-if="managerCountSortOrder !== 'none'"
                class="admin-schools-sort-header__dir"
                aria-hidden="true"
              >
                {{ sortTriangle(managerCountSortOrder) }}
              </span>
            </button>
          </template>
          <template #default="{ row }">
            <span class="tabular-nums text-stone-700">{{ managerCountTotal(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.actions')"
          min-width="96"
          fixed="right"
          align="center"
          header-align="center"
        >
          <template #default="{ row }">
            <el-button
              v-if="canEditOrganizations"
              type="primary"
              plain
              size="small"
              class="admin-swiss-pill-btn admin-swiss-pill-btn--edit"
              @click="openTrendModal(row, 'general')"
            >
              <el-icon class="mr-0.5"><Edit /></el-icon>
              {{ t('common.edit') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <AdminTrendChartModal
      v-model:visible="trendModalVisible"
      type="org"
      :school-dialog-mode="schoolDialogMode"
      :org-name="trendOrg?.name"
      :org-id="trendOrg?.id"
      :org-display-name="trendOrg?.display_name"
      :org-is-active="trendOrg?.is_active"
      :org-user-count="trendOrg?.user_count ?? 0"
      :org-expires-at="trendOrg?.expires_at"
      :org-school-tier="trendOrg?.school_tier"
      :org-extra-member-seats="trendOrg?.extra_member_seats ?? 0"
      :org-dify-api-base-url="trendOrg?.dify_api_base_url"
      :org-dify-api-key-masked="trendOrg?.dify_api_key_masked"
      :org-dify-api-base-url2="trendOrg?.dify_api_base_url_2"
      :org-dify-api-key2-masked="trendOrg?.dify_api_key_2_masked"
      :org-dify-active-server="trendOrg?.dify_active_server"
      :org-dify-failover-enabled="trendOrg?.dify_failover_enabled"
      :org-dify-timeout-seconds="trendOrg?.dify_timeout_seconds"
      :org-dingtalk-ai-card-streaming-max-chars="trendOrg?.dingtalk_ai_card_streaming_max_chars"
      :org-show-chain-of-thought="trendOrg?.show_chain_of_thought"
      :org-mindmate-agent-name="trendOrg?.mindmate_agent_name"
      :org-mindmate-agent-avatar-url="trendOrg?.mindmate_agent_avatar_url"
      :initial-school-tab="trendOrg?.initial_tab"
      :initial-trend-period="trendOrg?.initial_trend_period ?? 'week'"
      :read-only="!canEditOrganizations"
      @refresh="() => loadSchools({ silent: true })"
    />

    <AdminSchoolCreateDialog
      v-model="createModalVisible"
      @created="onSchoolCreated"
    />

    <AdminSchoolShareDialog
      v-model="shareModalVisible"
      :invitation-code="shareInvitationCode"
      :organization-name="shareOrganizationName"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
