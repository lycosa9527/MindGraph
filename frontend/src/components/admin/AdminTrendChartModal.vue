<script setup lang="ts">
/**
 * Admin Trend Chart Modal - Reusable chart + token cards for org/user
 * Used by Schools and Users tabs when clicking a row
 * For org type: also shows invitation code (with refresh) and managers
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { Chart, type ChartConfiguration } from 'chart.js/auto'

import { Loading, Refresh, Share } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
  type: 'org' | 'user'
  orgName?: string
  orgId?: number
  orgInvitationCode?: string
  userName?: string
  userId?: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'refresh'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()

const chartTitle = ref('')
const chartLoading = ref(false)
const chartRef = ref<HTMLCanvasElement | null>(null)
let chartInstance: Chart<'line'> | null = null

const periodCards = ref({ today: '-', week: '-', month: '-', total: '-' })
const period = ref<'today' | 'week' | 'month' | 'total'>('week')

const invitationCode = ref('')
const managers = ref<{ id: number; phone: string; name: string }[]>([])
const orgUsers = ref<{ id: number; phone: string; name: string }[]>([])
const managersLoading = ref(false)
const addManagerUserId = ref<number | null>(null)
const addManagerSelect = ref<number | null>(null)
const refreshCodeLoading = ref(false)

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function formatChartLabel(value: number): string {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M'
  if (value >= 1000) return (value / 1000).toFixed(1) + 'K'
  return String(value)
}

function close() {
  emit('update:visible', false)
}

function handleClose() {
  chartInstance?.destroy()
  chartInstance = null
}

async function loadOrgChart() {
  if (props.orgName == null) return
  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period.value]
  const hourly = period.value === 'today'
  let params = `days=${days}&hourly=${hourly}`
  if (props.orgId != null) {
    params += `&organization_id=${props.orgId}`
  } else {
    params += `&organization_name=${encodeURIComponent(props.orgName)}`
  }
  const res = await apiRequest(`/api/auth/admin/stats/trends/organization?${params}`)
  if (!res.ok) throw new Error('Failed to load')
  return res.json()
}

async function loadUserChart() {
  if (props.userId == null) return
  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period.value]
  const res = await apiRequest(
    `/api/auth/admin/stats/trends/user?user_id=${props.userId}&days=${days}`
  )
  if (!res.ok) throw new Error('Failed to load')
  return res.json()
}

async function loadOrgTokenCards() {
  if (props.orgId == null) return
  const res = await apiRequest(`/api/auth/admin/token-stats?organization_id=${props.orgId}`)
  if (!res.ok) return
  const data = await res.json()
  const fmt = (p: { input_tokens?: number; output_tokens?: number }) => {
    const i = p?.input_tokens ?? 0
    const o = p?.output_tokens ?? 0
    return `${formatNumber(i)}+${formatNumber(o)}`
  }
  periodCards.value = {
    today: fmt(data.today),
    week: fmt(data.past_week),
    month: fmt(data.past_month),
    total: fmt(data.total),
  }
}

async function loadUserTokenCards() {
  if (props.userId == null) return
  const res = await apiRequest(
    `/api/auth/admin/stats/trends/user?user_id=${props.userId}&days=0`
  )
  if (!res.ok) return
  const data = await res.json()
  const arr = data?.data ?? []
  const sum = (n: number) =>
    arr.slice(-n).reduce((a: number, b: { value?: number }) => a + (b.value ?? 0), 0)
  periodCards.value = {
    today: formatNumber(sum(1) || 0),
    week: formatNumber(sum(7) || 0),
    month: formatNumber(sum(30) || 0),
    total: formatNumber(arr.reduce((a: number, b: { value?: number }) => a + (b.value ?? 0), 0)),
  }
}

function renderChart(
  data: { data: Array<{ date: string; value: number; input?: number; output?: number }> }
) {
  if (!chartRef.value) return
  const rawData = data?.data ?? []
  if (rawData.length === 0) return

  chartInstance?.destroy()
  chartInstance = null

  const labels = rawData.map((item) => {
    const dateStr = item.date.includes(' ')
      ? item.date.replace(' ', 'T')
      : item.date + 'T00:00:00'
    const date = new Date(dateStr)
    if (item.date.includes(':') && item.date.includes(' ')) {
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        hour12: false,
        timeZone: 'Asia/Shanghai',
      })
    }
    return date.toLocaleDateString('en-US', {
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
    rawData[0] &&
    (rawData[0].input !== undefined || rawData[0].output !== undefined)

  const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
    {
      label: chartTitle.value,
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
            label: (ctx) =>
              `${ctx.dataset.label}: ${formatChartLabel(Number(ctx.raw))}`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          min: yMin,
          max: yMax,
          ticks: { callback: (val) => formatChartLabel(Number(val)) },
        },
        x: { ticks: { maxRotation: 45, minRotation: 45 } },
      },
    },
  }
  chartInstance = new Chart(chartRef.value, config)
}

async function load() {
  if (!props.visible) return
  if (props.type === 'org' && !props.orgName) return
  if (props.type === 'user' && props.userId == null) return
  chartLoading.value = true
  periodCards.value = { today: '-', week: '-', month: '-', total: '-' }
  try {
    if (props.type === 'org') {
      chartTitle.value = `${t('admin.trendOrgTokens')}: ${props.orgName ?? ''}`
      const data = await loadOrgChart()
      chartLoading.value = false
      await nextTick()
      await new Promise((r) => setTimeout(r, 50))
      if (data) renderChart(data)
      await loadOrgTokenCards()
    } else {
      chartTitle.value = `${t('admin.trendUserTokens')}: ${props.userName ?? ''}`
      const data = await loadUserChart()
      chartLoading.value = false
      await nextTick()
      await new Promise((r) => setTimeout(r, 50))
      if (data) renderChart(data)
      await loadUserTokenCards()
    }
  } catch {
    notify.error(t('admin.dashboardLoadError'))
    chartLoading.value = false
  }
}

async function switchPeriod(p: 'today' | 'week' | 'month' | 'total') {
  period.value = p
  await load()
}

async function loadManagersAndUsers() {
  if (props.type !== 'org' || props.orgId == null) return
  invitationCode.value = props.orgInvitationCode ?? ''
  managersLoading.value = true
  try {
    const [managersRes, usersRes] = await Promise.all([
      apiRequest(`/api/auth/admin/organizations/${props.orgId}/managers`),
      apiRequest(`/api/auth/admin/organizations/${props.orgId}/users`),
    ])
    if (managersRes.ok) {
      const mData = await managersRes.json()
      managers.value = mData.managers ?? []
    }
    if (usersRes.ok) {
      const uData = await usersRes.json()
      const users = uData.users ?? []
      const managerIds = new Set(managers.value.map((x) => x.id))
      orgUsers.value = users
        .filter(
          (u: { id: number; is_manager?: boolean }) =>
            !managerIds.has(u.id) && !u.is_manager
        )
        .map((u: { id: number; phone?: string; name?: string }) => ({
          id: u.id,
          phone: u.phone ?? '',
          name: u.name ?? u.phone ?? '',
        }))
    }
  } catch {
    managers.value = []
    orgUsers.value = []
  } finally {
    managersLoading.value = false
  }
}

async function refreshInvitationCode() {
  if (props.orgId == null) return
  refreshCodeLoading.value = true
  try {
    const res = await apiRequest(
      `/api/auth/admin/organizations/${props.orgId}/refresh-invitation-code`,
      { method: 'POST' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to refresh')
      return
    }
    const data = await res.json()
    invitationCode.value = data.invitation_code ?? invitationCode.value
    notify.success(t('notification.saved'))
    emit('refresh')
  } catch {
    notify.error('Failed to refresh invitation code')
  } finally {
    refreshCodeLoading.value = false
  }
}

async function setManager(userId: number) {
  if (props.orgId == null) return
  addManagerUserId.value = userId
  try {
    const res = await apiRequest(
      `/api/auth/admin/organizations/${props.orgId}/managers/${userId}`,
      { method: 'PUT' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to set manager')
      return
    }
    notify.success(t('notification.saved'))
    addManagerSelect.value = null
    await loadManagersAndUsers()
  } catch {
    notify.error('Failed to set manager')
  } finally {
    addManagerUserId.value = null
  }
}

async function removeManager(userId: number) {
  if (props.orgId == null) return
  try {
    const res = await apiRequest(
      `/api/auth/admin/organizations/${props.orgId}/managers/${userId}`,
      { method: 'DELETE' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || 'Failed to remove manager')
      return
    }
    notify.success(t('notification.saved'))
    await loadManagersAndUsers()
  } catch {
    notify.error('Failed to remove manager')
  }
}

function shareMessageText(): string {
  return t('admin.shareInviteMessage').replace('{code}', invitationCode.value)
}

async function copyShareMessage() {
  try {
    await navigator.clipboard.writeText(shareMessageText())
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      load()
      if (props.type === 'org' && props.orgId) {
        invitationCode.value = props.orgInvitationCode ?? ''
        loadManagersAndUsers()
      }
    } else {
      chartInstance?.destroy()
      chartInstance = null
    }
  }
)

watch(
  () => [props.orgId, props.orgName, props.orgInvitationCode, props.userId, props.userName] as const,
  () => {
    if (props.visible) {
      load()
      if (props.type === 'org' && props.orgId) {
        invitationCode.value = props.orgInvitationCode ?? ''
        loadManagersAndUsers()
      }
    }
  }
)

onBeforeUnmount(() => {
  chartInstance?.destroy()
  chartInstance = null
})
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="chartTitle"
    width="640px"
    destroy-on-close
    @update:model-value="(v: boolean) => emit('update:visible', v)"
    @close="handleClose"
  >
    <div
      v-if="chartLoading"
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
          ref="chartRef"
          class="block w-full h-full"
        />
      </div>
      <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <el-card
            shadow="hover"
            class="token-period-card cursor-pointer"
            :class="{ 'ring-2 ring-primary-500': period === 'today' }"
            @click="switchPeriod('today')"
          >
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {{ t('admin.today') }}
            </p>
            <p class="text-lg font-bold text-gray-800 dark:text-white">
              {{ periodCards.today }}
            </p>
          </el-card>
          <el-card
            shadow="hover"
            class="token-period-card cursor-pointer"
            :class="{ 'ring-2 ring-primary-500': period === 'week' }"
            @click="switchPeriod('week')"
          >
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {{ t('admin.pastWeek') }}
            </p>
            <p class="text-lg font-bold text-gray-800 dark:text-white">
              {{ periodCards.week }}
            </p>
          </el-card>
          <el-card
            shadow="hover"
            class="token-period-card cursor-pointer"
            :class="{ 'ring-2 ring-primary-500': period === 'month' }"
            @click="switchPeriod('month')"
          >
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {{ t('admin.pastMonth') }}
            </p>
            <p class="text-lg font-bold text-gray-800 dark:text-white">
              {{ periodCards.month }}
            </p>
          </el-card>
          <el-card
            shadow="hover"
            class="token-period-card cursor-pointer"
            :class="{ 'ring-2 ring-primary-500': period === 'total' }"
            @click="switchPeriod('total')"
          >
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {{ t('admin.allTime') }}
            </p>
            <p class="text-lg font-bold text-gray-800 dark:text-white">
              {{ periodCards.total }}
            </p>
          </el-card>
        </div>
      </div>

      <div
        v-if="type === 'org' && orgId"
        class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 space-y-4"
      >
        <div class="flex items-center justify-between">
          <span class="text-sm font-medium">{{ t('admin.invitationCode') }}</span>
          <div class="flex items-center gap-2">
            <el-tag type="info">{{ invitationCode }}</el-tag>
            <el-button
              :loading="refreshCodeLoading"
              size="small"
              @click="refreshInvitationCode"
            >
              <el-icon class="mr-1"><Refresh /></el-icon>
              {{ t('admin.refreshInvitationCode') }}
            </el-button>
            <el-tooltip :content="t('admin.shareInviteTitle')" placement="top">
              <el-button
                size="small"
                @click="copyShareMessage"
              >
                <el-icon><Share /></el-icon>
              </el-button>
            </el-tooltip>
          </div>
        </div>

        <div>
          <p class="text-sm font-medium mb-2">{{ t('admin.managers') }}</p>
          <div
            v-if="managersLoading"
            class="text-gray-500 text-sm"
          >
            {{ t('admin.loading') }}
          </div>
          <div
            v-else
            class="space-y-2"
          >
            <div
              v-for="m in managers"
              :key="m.id"
              class="flex items-center justify-between py-1 px-2 rounded bg-gray-50 dark:bg-gray-800"
            >
              <span>{{ m.name || m.phone }}</span>
              <el-button
                type="danger"
                link
                size="small"
                @click="removeManager(m.id)"
              >
                {{ t('admin.removeManager') }}
              </el-button>
            </div>
            <div
              v-if="orgUsers.length > 0"
              class="flex items-center gap-2 mt-2"
            >
              <el-select
                v-model="addManagerSelect"
                :placeholder="t('admin.setManager')"
                size="small"
                style="width: 200px"
                clearable
                @change="(v: number | null) => v != null && setManager(v)"
              >
                <el-option
                  v-for="u in orgUsers"
                  :key="u.id"
                  :label="u.name || u.phone"
                  :value="u.id"
                />
              </el-select>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template #footer>
      <el-button @click="close">{{ t('common.close') }}</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.token-period-card :deep(.el-card__body) {
  padding: 12px 16px;
}
</style>
