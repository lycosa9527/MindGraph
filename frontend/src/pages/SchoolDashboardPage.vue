<script setup lang="ts">
/**
 * School Dashboard - Org-scoped dashboard for managers (principals)
 * Admins can use dropdown to preview any school's dashboard
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  Connection,
  DocumentCopy,
  FolderOpened,
  Key,
  Loading,
  Plus,
  Stamp,
  User,
} from '@element-plus/icons-vue'

import type { Chart as ChartInstance } from 'chart.js'

import SchoolDashboardOrgPicker from '@/components/school/SchoolDashboardOrgPicker.vue'
import SchoolDashboardQuotaCard from '@/components/school/SchoolDashboardQuotaCard.vue'
import SchoolDashboardUsersTab from '@/components/school/SchoolDashboardUsersTab.vue'
import SchoolAddMemberDialog from '@/components/school/SchoolAddMemberDialog.vue'
import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import AdminTokenUsageByServicePanel from '@/components/admin/AdminTokenUsageByServicePanel.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { queryErrorMessage } from '@/composables/admin/useQueryErrorNotification'
import { useSchoolDashboardStats } from '@/composables/admin/useSchoolDashboardStats'
import { useScopedAbort } from '@/composables/core/useScopedAbort'
import { useAdminOrgScope } from '@/composables/admin/useAdminOrgScope'
import {
  useSchoolDashboardQuotas,
} from '@/composables/school/useSchoolDashboardQuotas'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import {
  fetchAdminSchoolTokenStats,
  fetchAdminSchoolTrends,
} from '@/composables/queries'
import { useAuthStore } from '@/stores'
import { isManagerAssignmentUnavailable, isUnlimitedMemberLimit } from '@/constants/schoolTier'
import { type ChartConfiguration, type TooltipItem, loadChartJs } from '@/utils/lazyChartJs'

const { t, isZh } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const props = withDefaults(
  defineProps<{
    embedded?: boolean
  }>(),
  { embedded: false }
)

const authStore = useAuthStore()
const { loadCapabilities, can, isReadOnly } = useAdminAccess()
const { effectiveOrgId, refetchOrganizations, syncSelectedOrgFromUser, showPicker, effectiveOrgName } =
  useAdminOrgScope()
const { on: onAdminEvent, emit: emitAdminEvent } = useAdminEventBus('SchoolDashboardPage')
const { beginRequest: beginTrendRequest, abort: abortTrendRequests } = useScopedAbort()

const effectiveOrgIdRef = computed(() => effectiveOrgId.value)
const { isLoading, stats, topUsers, loadStats } = useSchoolDashboardStats(effectiveOrgIdRef)

const addMemberVisible = ref(false)

const showAddMemberButton = computed(
  () =>
    effectiveOrgId.value != null &&
    !isReadOnly.value &&
    (can('tab.users.edit') ||
      (can('scope.org') && (can('tab.school_dashboard.view') || can('tab.data_center.view'))))
)

function onMemberCreated(): void {
  void loadStats()
  emitAdminEvent('admin:mutation_completed', { domain: 'school_users' })
}

const addMemberSchoolName = computed(() =>
  (stats.value.organization?.name || effectiveOrgName.value || authStore.user?.schoolName || '').trim()
)
const {
  storageUsedGb,
  storageLimitGb,
  storageUsedLabel,
  storageLimitLabel,
  storageRemainingLabel,
  memberRemaining,
  managerRemaining,
} = useSchoolDashboardQuotas(computed(() => stats.value.quotas))

const trendModalVisible = ref(false)
const trendChartTitle = ref('')
const trendChartLoading = ref(false)
const trendChartRef = ref<HTMLCanvasElement | null>(null)
let trendChartInstance: ChartInstance<'line'> | null = null
const periodCards = ref({ today: '-', week: '-', month: '-', total: '-' })
const trendPeriod = ref<'today' | 'week' | 'month' | 'total'>('week')

const activeTab = ref<'overview' | 'tokens' | 'users'>('overview')

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

const invitationCodeDisplay = computed(
  () => (stats.value.organization?.invitation_code || '').trim() || '—'
)

async function copyInvitationCode(event: MouseEvent) {
  event.stopPropagation()
  const code = (stats.value.organization?.invitation_code || '').trim()
  if (!code) return
  const text = t('admin.schoolInviteCopyPayload', {
    siteUrl: publicSiteUrl.value,
    code,
  })
  try {
    await navigator.clipboard.writeText(text)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

function formatChartLabel(value: number): string {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M'
  if (value >= 1000) return (value / 1000).toFixed(1) + 'K'
  return String(value)
}

async function showTrendChart(period: 'today' | 'week' | 'month' | 'total' = 'week') {
  const orgId = effectiveOrgId.value
  if (orgId == null) return
  trendPeriod.value = period
  trendChartTitle.value = `${t('admin.trendOrgTokens')}: ${stats.value.organization?.name ?? ''}`
  trendModalVisible.value = true
  trendChartLoading.value = true

  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period]
  const hourly = period === 'today'
  const signal = beginTrendRequest()
  try {
    const [chartData, tokenData] = await Promise.all([
      fetchAdminSchoolTrends({ organization_id: orgId, days, hourly }, signal),
      fetchAdminSchoolTokenStats(orgId, signal),
    ])
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    await renderTrendChart({ data: chartData.data ?? [] })
    if (tokenData) {
      const fmt = (p: { input_tokens?: number; output_tokens?: number }) => {
        const i = p?.input_tokens ?? 0
        const o = p?.output_tokens ?? 0
        return `${formatNumber(i)}+${formatNumber(o)}`
      }
      periodCards.value = {
        today: fmt(tokenData.today),
        week: fmt(tokenData.past_week),
        month: fmt(tokenData.past_month),
        total: fmt(tokenData.total),
      }
    }
  } catch (err) {
    const message = queryErrorMessage(err, t('admin.dashboardLoadError'))
    if (message) {
      notify.error(message)
    }
    trendChartLoading.value = false
  }
}

async function renderTrendChart(data: {
  data: Array<{ date: string; value: number; input?: number; output?: number }>
}) {
  if (!trendChartRef.value) return
  const rawData = data?.data ?? []
  if (rawData.length === 0) return

  trendChartInstance?.destroy()
  trendChartInstance = null

  const chartLocale = isZh.value ? 'zh-CN' : 'en-US'
  const labels = rawData.map((item) => {
    const dateStr = item.date.includes(' ') ? item.date.replace(' ', 'T') : item.date + 'T00:00:00'
    const date = new Date(dateStr)
    if (item.date.includes(':') && item.date.includes(' ')) {
      return date.toLocaleString(chartLocale, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        hour12: false,
        timeZone: 'Asia/Shanghai',
      })
    }
    return date.toLocaleDateString(chartLocale, {
      month: 'short',
      day: 'numeric',
      timeZone: 'Asia/Shanghai',
    })
  })

  const values = rawData.map((item) => item.value)
  const maxVal = Math.max(...values, 0)
  const minVal = Math.min(...values, 0)
  const range = maxVal - minVal
  const padding = range === 0 ? maxVal * 0.1 : range * 0.1
  const yMin = Math.max(0, minVal - padding)
  const yMax = maxVal + padding

  const hasInputOutput =
    rawData[0] && (rawData[0].input !== undefined || rawData[0].output !== undefined)

  const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
    {
      label: trendChartTitle.value,
      data: values,
      borderColor: '#667eea',
      backgroundColor: 'rgba(102, 126, 234, 0.1)',
      borderWidth: 2,
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
    },
  ]
  if (hasInputOutput) {
    datasets.push({
      label: t('admin.inputTokens'),
      data: rawData.map((item) => item.input ?? 0),
      borderColor: '#10b981',
      backgroundColor: 'rgba(16, 185, 129, 0.1)',
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 2,
      pointHoverRadius: 4,
    })
    datasets.push({
      label: t('admin.outputTokens'),
      data: rawData.map((item) => item.output ?? 0),
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245, 158, 11, 0.1)',
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 2,
      pointHoverRadius: 4,
    })
  }

  const config: ChartConfiguration<'line'> = {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: hasInputOutput, position: 'top' },
        tooltip: {
          callbacks: {
            label: (ctx: TooltipItem<'line'>) =>
              `${ctx.dataset.label}: ${formatChartLabel(Number(ctx.raw))}`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          min: yMin,
          max: yMax,
          ticks: { callback: (val: string | number) => formatChartLabel(Number(val)) },
        },
        x: { ticks: { maxRotation: 45, minRotation: 45 } },
      },
    },
  }
  const Chart = await loadChartJs()
  trendChartInstance = new Chart(trendChartRef.value, config)
}

function switchTrendPeriod(period: 'today' | 'week' | 'month' | 'total') {
  showTrendChart(period)
}

function closeTrendModal() {
  abortTrendRequests()
  trendModalVisible.value = false
  trendChartInstance?.destroy()
  trendChartInstance = null
}

onAdminEvent('admin:toolbar_action', (payload) => {
  if (
    payload.action === 'open_add_school_member' &&
    props.embedded &&
    showAddMemberButton.value
  ) {
    addMemberVisible.value = true
  }
})

watch(
  () => [authStore.adminCapabilitiesLoaded, authStore.user?.schoolId] as const,
  () => {
    syncSelectedOrgFromUser()
  }
)

onMounted(async () => {
  await loadCapabilities()
  syncSelectedOrgFromUser()
  await refetchOrganizations()
  syncSelectedOrgFromUser()
})

onBeforeUnmount(() => {
  trendChartInstance?.destroy()
  trendChartInstance = null
})
</script>

<template>
  <div
    class="school-dashboard flex flex-col min-h-0 min-w-0"
    :class="
      embedded
        ? 'school-dashboard--embedded'
        : 'school-dashboard--standalone flex-1 bg-stone-50 overflow-hidden'
    "
  >
    <div
      v-if="!embedded"
      class="school-header h-14 px-4 flex items-center justify-between gap-3 bg-white border-b border-stone-200 shrink-0"
    >
      <h1 class="text-sm font-semibold text-stone-900 truncate min-w-0">
        {{ t('admin.schoolDashboard') }}
      </h1>
      <div class="flex items-center gap-2 shrink-0">
        <el-button
          v-if="showAddMemberButton"
          type="primary"
          round
          class="school-add-member-btn admin-swiss-btn"
          @click="addMemberVisible = true"
        >
          <el-icon class="el-icon--left"><Plus /></el-icon>
          {{ t('admin.schoolAddMemberButton') }}
        </el-button>
        <SchoolDashboardOrgPicker
          v-if="showPicker"
          compact
        />
      </div>
    </div>

    <div
      class="school-body min-w-0"
      :class="embedded ? 'school-body--embedded' : 'school-body--standalone flex-1 overflow-y-auto p-6'"
    >
      <div
        v-if="effectiveOrgId == null && !isLoading"
        class="text-center py-20 text-gray-500"
      >
        <p>{{ t('admin.schoolDashboardNoOrg') }}</p>
      </div>

      <template v-else-if="effectiveOrgId != null">
        <el-tabs
          v-model="activeTab"
          class="school-tabs admin-swiss-tabs"
        >
          <el-tab-pane
            :label="t('admin.dashboard')"
            name="overview"
          />
          <el-tab-pane
            :label="t('admin.tokens')"
            name="tokens"
          />
          <el-tab-pane
            :label="t('admin.schoolUsersTab')"
            name="users"
          />
        </el-tabs>

        <div
          v-if="activeTab === 'overview' && isLoading"
          class="flex justify-center py-20"
        >
          <el-icon
            class="is-loading"
            :size="32"
          >
            <Loading />
          </el-icon>
        </div>

        <template v-else-if="activeTab === 'overview'">
          <div
            class="grid grid-cols-1 md:grid-cols-3 gap-6"
            :class="embedded ? 'pt-0' : 'pt-4'"
          >
            <SchoolDashboardQuotaCard
              :title="t('admin.memberSeats')"
              :used="stats.quotas.memberCount"
              :limit="stats.quotas.memberLimit"
              :limit-display-override="
                isUnlimitedMemberLimit(stats.quotas.memberLimit) ? t('admin.unlimited') : ''
              "
              :remaining-label="
                memberRemaining === null
                  ? t('admin.unlimitedMembers')
                  : t('admin.seatsRemaining', { count: memberRemaining.toLocaleString() })
              "
              :icon="User"
              accent="blue"
            />
            <SchoolDashboardQuotaCard
              :title="t('admin.managerSeats')"
              :used="stats.quotas.managerCount"
              :limit="stats.quotas.managerLimit"
              :limit-display-override="
                isManagerAssignmentUnavailable(stats.quotas.managerLimit)
                  ? t('admin.noSchoolManagersShort')
                  : ''
              "
              :remaining-label="
                managerRemaining === null
                  ? t('admin.schoolManagerNotAvailableTrial')
                  : t('admin.seatsRemaining', { count: managerRemaining.toLocaleString() })
              "
              :icon="Stamp"
              accent="purple"
            />
            <SchoolDashboardQuotaCard
              :title="t('admin.resourceSpace')"
              :used="storageUsedGb"
              :limit="storageLimitGb"
              :used-display-override="storageUsedLabel"
              :limit-display-override="storageLimitLabel"
              :remaining-label="
                t('admin.storageRemaining', {
                  amount: storageRemainingLabel,
                })
              "
              :icon="FolderOpened"
              accent="orange"
            />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <AdminSwissKpiCard
              :title="`${t('admin.tokens')} (${t('admin.pastWeek')})`"
              :value="formatNumber(stats.totalTokens)"
              :icon="Connection"
              theme="storage"
              clickable
              @click="showTrendChart('week')"
            />
            <AdminSwissKpiCard
              :title="t('admin.invitationCode')"
              :value="invitationCodeDisplay"
              :icon="Key"
              theme="managers"
            >
              <template #footer>
                <el-button
                  type="primary"
                  size="small"
                  round
                  class="self-start !rounded-full"
                  :disabled="!(stats.organization?.invitation_code || '').trim()"
                  @click="copyInvitationCode"
                >
                  <el-icon class="el-icon--left">
                    <DocumentCopy />
                  </el-icon>
                  {{ t('admin.copyShareMessage') }}
                </el-button>
              </template>
            </AdminSwissKpiCard>
          </div>

          <el-card
            v-if="topUsers.length > 0"
            shadow="hover"
            class="mt-6"
          >
            <template #header>
              <div class="flex items-center justify-between gap-2 w-full">
                <span class="font-medium">{{ t('admin.topUsersByTokens') }}</span>
                <el-button
                  text
                  size="small"
                  @click="loadStats"
                >
                  {{ t('common.refresh') }}
                </el-button>
              </div>
            </template>
            <el-table
              :data="topUsers"
              stripe
              size="small"
            >
              <el-table-column
                prop="name"
                :label="t('admin.name')"
              />
              <el-table-column
                prop="phone"
                :label="t('admin.phone')"
                width="140"
              />
              <el-table-column
                prop="total_tokens"
                :label="t('admin.tokensUsed')"
                width="120"
              >
                <template #default="{ row }">
                  {{ formatNumber(row.total_tokens) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </template>

        <!-- Token Usage Tab -->
        <template v-else-if="activeTab === 'tokens'">
          <div class="mt-4 mb-6">
            <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
              {{ t('admin.tokenUsageByService') }} - {{ stats.organization?.name }}
            </h2>
            <p class="text-sm text-gray-500">
              {{ t('admin.tokenUsageCompare') }}
            </p>
          </div>
          <AdminTokenUsageByServicePanel
            v-if="effectiveOrgId != null"
            :organization-id="effectiveOrgId"
            use-school-stats-endpoint
            show-overall-summary
          />
        </template>

        <template v-else-if="activeTab === 'users'">
          <SchoolDashboardUsersTab
            v-if="effectiveOrgId != null"
            :org-id="effectiveOrgId"
          />
        </template>
      </template>
    </div>

    <el-dialog
      v-model="trendModalVisible"
      :title="trendChartTitle"
      width="640px"
      destroy-on-close
      @close="closeTrendModal"
    >
      <div
        v-if="trendChartLoading"
        class="flex justify-center items-center h-64"
      >
        <el-icon
          class="is-loading"
          :size="32"
        >
          <Loading />
        </el-icon>
      </div>
      <template v-else>
        <div class="relative h-64 min-h-[256px] w-full">
          <canvas
            ref="trendChartRef"
            class="block w-full h-full"
          />
        </div>
        <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <AdminSwissPeriodCard
              :label="t('admin.today')"
              :value="periodCards.today"
              :active="trendPeriod === 'today'"
              theme="storage"
              @click="switchTrendPeriod('today')"
            />
            <AdminSwissPeriodCard
              :label="t('admin.pastWeek')"
              :value="periodCards.week"
              :active="trendPeriod === 'week'"
              theme="storage"
              @click="switchTrendPeriod('week')"
            />
            <AdminSwissPeriodCard
              :label="t('admin.pastMonth')"
              :value="periodCards.month"
              :active="trendPeriod === 'month'"
              theme="storage"
              @click="switchTrendPeriod('month')"
            />
            <AdminSwissPeriodCard
              :label="t('admin.allTime')"
              :value="periodCards.total"
              :active="trendPeriod === 'total'"
              theme="storage"
              @click="switchTrendPeriod('total')"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="closeTrendModal">{{ t('common.close') }}</el-button>
      </template>
    </el-dialog>

    <SchoolAddMemberDialog
      v-if="effectiveOrgId != null"
      v-model:visible="addMemberVisible"
      :org-id="effectiveOrgId"
      :school-name="addMemberSchoolName"
      @created="onMemberCreated"
    />
  </div>
</template>

<style scoped>
.school-dashboard--embedded {
  background: transparent;
}

.school-body--standalone {
  min-height: 0;
}

.school-dashboard--embedded .admin-swiss-tabs :deep(.el-tabs__header) {
  margin-top: 0;
}

.school-add-member-btn.el-button {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-text-color: #fafaf9;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
}

</style>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
