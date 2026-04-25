<script setup lang="ts">
/**
 * Admin Trend Chart Modal - Reusable chart + token cards for org/user
 * Used by Schools and Users tabs when clicking a row
 * For org type: also shows invitation code (with refresh) and managers
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'

import { Delete, Hide, Loading, Lock, Refresh, Share, Unlock, View } from '@element-plus/icons-vue'

import { Chart, type ChartConfiguration, type TooltipItem, registerables } from 'chart.js'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { useUIStore } from '@/stores/ui'
import { apiRequest } from '@/utils/apiClient'

Chart.register(...registerables)

const props = defineProps<{
  visible: boolean
  type: 'org' | 'user'
  orgName?: string
  orgId?: number
  orgInvitationCode?: string
  orgDisplayName?: string
  orgIsActive?: boolean
  orgUserCount?: number
  orgExpiresAt?: string | null
  userName?: string
  userId?: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'refresh'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()
const uiStore = useUIStore()

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
const displayNameEdit = ref('')
const displayNameSaving = ref(false)
const orgActiveState = ref(true)
const lockLoading = ref(false)
const deleteLoading = ref(false)
const expiresAtEdit = ref<string | null>(null)
const expiresAtSaving = ref(false)

/** True when invitationCode holds the full code (after reveal or refresh); list API is masked only. */
const revealInvitation = ref(false)

function isLikelyMaskedInviteCode(code: string | undefined | null): boolean {
  if (code == null || code === '') {
    return false
  }
  return code.includes('*')
}

/**
 * List/parent org props use masked codes; do not replace a revealed full code with a masked value.
 */
function applyInvitationCodeFromProps(): void {
  const fromProp = props.orgInvitationCode ?? ''
  if (
    !isLikelyMaskedInviteCode(fromProp) ||
    isLikelyMaskedInviteCode(invitationCode.value) ||
    invitationCode.value === ''
  ) {
    invitationCode.value = fromProp
  }
}

async function toggleRevealInvitation() {
  if (revealInvitation.value) {
    revealInvitation.value = false
    invitationCode.value = props.orgInvitationCode ?? ''
    return
  }
  if (props.orgId == null) return
  try {
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}/invitation-code`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.refreshFailed'))
      return
    }
    const data = (await res.json()) as { invitation_code?: string }
    invitationCode.value = data.invitation_code ?? ''
    revealInvitation.value = true
  } catch {
    notify.error(t('admin.trendChartErrors.refreshInvitationCodeFailed'))
  }
}

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

function parseExpiresAtToDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})/)
  return m ? m[1] : null
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
  const res = await apiRequest(`/api/auth/admin/stats/trends/user?user_id=${props.userId}&days=0`)
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

function renderChart(data: {
  data: Array<{ date: string; value: number; input?: number; output?: number }>
}) {
  if (!chartRef.value) return
  const rawData = data?.data ?? []
  if (rawData.length === 0) return

  chartInstance?.destroy()
  chartInstance = null

  const intlLocale = intlLocaleForUiCode(uiStore.language)
  const labels = rawData.map((item) => {
    const dateStr = item.date.includes(' ') ? item.date.replace(' ', 'T') : item.date + 'T00:00:00'
    const date = new Date(dateStr)
    if (item.date.includes(':') && item.date.includes(' ')) {
      return date.toLocaleString(intlLocale, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        hour12: false,
        timeZone: 'Asia/Shanghai',
      })
    }
    return date.toLocaleDateString(intlLocale, {
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
  applyInvitationCodeFromProps()
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
        .filter((u: { id: number; is_manager?: boolean }) => !managerIds.has(u.id) && !u.is_manager)
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
      notify.error((data.detail as string) || t('admin.trendChartErrors.refreshFailed'))
      return
    }
    const data = await res.json()
    invitationCode.value = data.invitation_code ?? invitationCode.value
    revealInvitation.value = true
    notify.success(t('notification.saved'))
    emit('refresh')
  } catch {
    notify.error(t('admin.trendChartErrors.refreshInvitationCodeFailed'))
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
      notify.error((data.detail as string) || t('admin.trendChartErrors.setManagerFailed'))
      return
    }
    notify.success(t('notification.saved'))
    addManagerSelect.value = null
    await loadManagersAndUsers()
  } catch {
    notify.error(t('admin.trendChartErrors.setManagerFailed'))
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
      notify.error((data.detail as string) || t('admin.trendChartErrors.removeManagerFailed'))
      return
    }
    notify.success(t('notification.saved'))
    await loadManagersAndUsers()
  } catch {
    notify.error(t('admin.trendChartErrors.removeManagerFailed'))
  }
}

function shareMessageTextForCode(code: string): string {
  return t('admin.shareInviteMessage', {
    code,
    siteUrl: publicSiteUrl.value,
  })
}

async function copyShareMessage() {
  if (props.orgId == null) return
  try {
    let code = invitationCode.value
    if (!revealInvitation.value) {
      const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}/invitation-code`)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        notify.error((data.detail as string) || t('admin.trendChartErrors.refreshFailed'))
        return
      }
      const data = (await res.json()) as { invitation_code?: string }
      code = data.invitation_code ?? ''
    }
    await navigator.clipboard.writeText(shareMessageTextForCode(code))
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

async function saveExpiresAt() {
  if (props.orgId == null) return
  expiresAtSaving.value = true
  try {
    const dateVal = expiresAtEdit.value?.trim() || null
    const expiresAtPayload = dateVal ? `${dateVal}T23:59:59+08:00` : null
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}`, {
      method: 'PUT',
      body: JSON.stringify({ expires_at: expiresAtPayload }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.saveFailed'))
      return
    }
    notify.success(t('notification.saved'))
    emit('refresh')
  } catch {
    notify.error(t('admin.trendChartErrors.saveExpirationFailed'))
  } finally {
    expiresAtSaving.value = false
  }
}

async function saveDisplayName() {
  if (props.orgId == null) return
  displayNameSaving.value = true
  try {
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}`, {
      method: 'PUT',
      body: JSON.stringify({ display_name: displayNameEdit.value.trim() || null }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.saveFailed'))
      return
    }
    notify.success(t('notification.saved'))
    emit('refresh')
  } catch {
    notify.error(t('admin.trendChartErrors.saveDisplayNameFailed'))
  } finally {
    displayNameSaving.value = false
  }
}

async function toggleLock() {
  if (props.orgId == null) return
  lockLoading.value = true
  try {
    const newActive = !orgActiveState.value
    const res = await apiRequest(`/api/auth/admin/organizations/${props.orgId}`, {
      method: 'PUT',
      body: JSON.stringify({ is_active: newActive }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.updateFailed'))
      return
    }
    orgActiveState.value = newActive
    notify.success(t('notification.saved'))
    emit('refresh')
  } catch {
    notify.error(t('admin.trendChartErrors.updateOrgStatusFailed'))
  } finally {
    lockLoading.value = false
  }
}

async function deleteOrganization() {
  if (props.orgId == null) return
  const userCount = props.orgUserCount ?? 0
  const name = props.orgName ?? ''
  const confirmMsg =
    userCount > 0
      ? t('admin.deleteOrgConfirmWithUsers')
          .replace('{name}', name)
          .replace('{count}', String(userCount))
      : t('admin.deleteOrgConfirm').replace('{name}', name)
  try {
    await ElMessageBox.confirm(confirmMsg, t('admin.deleteOrganization'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }
  deleteLoading.value = true
  try {
    const url =
      userCount > 0
        ? `/api/auth/admin/organizations/${props.orgId}?delete_users=true`
        : `/api/auth/admin/organizations/${props.orgId}`
    const res = await apiRequest(url, { method: 'DELETE' })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.deleteRecordFailed'))
      return
    }
    notify.success(t('notification.saved'))
    emit('update:visible', false)
    emit('refresh')
  } catch {
    notify.error(t('admin.trendChartErrors.deleteOrgFailed'))
  } finally {
    deleteLoading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      revealInvitation.value = false
      void load()
      if (props.type === 'org' && props.orgId) {
        invitationCode.value = props.orgInvitationCode ?? ''
        displayNameEdit.value = props.orgDisplayName ?? ''
        orgActiveState.value = props.orgIsActive ?? true
        expiresAtEdit.value = parseExpiresAtToDate(props.orgExpiresAt)
        void loadManagersAndUsers()
      }
    } else {
      chartInstance?.destroy()
      chartInstance = null
    }
  }
)

watch(
  () =>
    [
      props.orgId,
      props.orgName,
      props.orgInvitationCode,
      props.orgDisplayName,
      props.orgIsActive,
      props.orgExpiresAt,
      props.userId,
      props.userName,
    ] as const,
  (newVal, oldVal) => {
    if (!props.visible) {
      return
    }
    const orgIdChanged = oldVal != null && newVal[0] !== oldVal[0]
    if (orgIdChanged) {
      revealInvitation.value = false
    }
    void load()
    if (props.type === 'org' && props.orgId) {
      if (orgIdChanged) {
        invitationCode.value = props.orgInvitationCode ?? ''
      } else {
        applyInvitationCodeFromProps()
      }
      displayNameEdit.value = props.orgDisplayName ?? ''
      orgActiveState.value = props.orgIsActive ?? true
      expiresAtEdit.value = parseExpiresAtToDate(props.orgExpiresAt)
      void loadManagersAndUsers()
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
    class="admin-org-dialog"
    width="720px"
    destroy-on-close
    align-center
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
      <div class="relative h-64 min-h-[220px] sm:min-h-[256px] w-full min-w-0">
        <canvas
          ref="chartRef"
          class="block w-full h-full"
        />
      </div>
      <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div class="grid grid-cols-1 min-[400px]:grid-cols-2 lg:grid-cols-4 gap-3">
          <el-card
            shadow="hover"
            class="token-period-card min-w-0 cursor-pointer"
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
            class="token-period-card min-w-0 cursor-pointer"
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
            class="token-period-card min-w-0 cursor-pointer"
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
            class="token-period-card min-w-0 cursor-pointer"
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
        <div>
          <p class="text-sm font-medium mb-2">{{ t('admin.displayNameLabel') }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
            {{ t('admin.displayNameHint') }}
          </p>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-stretch">
            <el-input
              v-model="displayNameEdit"
              :placeholder="orgName"
              size="small"
              clearable
              class="min-w-0 flex-1"
            />
            <el-button
              type="primary"
              size="small"
              class="admin-org-pill-btn shrink-0"
              :loading="displayNameSaving"
              @click="saveDisplayName"
            >
              {{ t('admin.save') }}
            </el-button>
          </div>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span class="text-sm font-medium shrink-0">{{ t('admin.status') }}</span>
          <div class="flex flex-wrap items-center gap-2 min-w-0">
            <el-tag
              :type="orgActiveState ? 'success' : 'danger'"
              size="small"
            >
              {{ orgActiveState ? t('admin.enabled') : t('admin.disabled') }}
            </el-tag>
            <el-button
              :loading="lockLoading"
              size="small"
              class="admin-org-pill-btn-muted"
              :type="orgActiveState ? 'warning' : 'success'"
              @click="toggleLock"
            >
              <el-icon class="mr-1">
                <Lock v-if="orgActiveState" />
                <Unlock v-else />
              </el-icon>
              {{ orgActiveState ? t('admin.lockOrganization') : t('admin.unlockOrganization') }}
            </el-button>
          </div>
        </div>
        <div>
          <p class="text-sm font-medium mb-2">{{ t('admin.expirationDate') }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
            {{ t('admin.expirationDateHint') }}
          </p>
          <div class="flex flex-col gap-2 sm:flex-row sm:items-stretch">
            <el-date-picker
              v-model="expiresAtEdit"
              type="date"
              :placeholder="t('admin.noExpiration')"
              value-format="YYYY-MM-DD"
              size="small"
              clearable
              class="min-w-0 flex-1"
            />
            <el-button
              type="primary"
              size="small"
              class="admin-org-pill-btn shrink-0"
              :loading="expiresAtSaving"
              @click="saveExpiresAt"
            >
              {{ t('admin.save') }}
            </el-button>
          </div>
        </div>
        <div>
          <p class="text-sm font-medium mb-1">{{ t('admin.invitationCode') }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
            {{ t('admin.invitationCodeMaskedHint') }}
          </p>
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div class="flex min-w-0 flex-wrap items-center gap-2">
              <el-tag
                type="info"
                class="font-mono text-xs max-w-full break-all !h-auto py-1"
              >
                {{ invitationCode }}
              </el-tag>
              <el-tooltip
                :content="revealInvitation ? t('admin.sensitiveHide') : t('admin.sensitiveReveal')"
                placement="top"
              >
                <el-button
                  link
                  type="primary"
                  size="small"
                  class="shrink-0"
                  @click="toggleRevealInvitation"
                >
                  <el-icon><Hide v-if="revealInvitation" /><View v-else /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
            <div class="flex flex-wrap items-center gap-2 shrink-0">
              <el-button
                :loading="refreshCodeLoading"
                size="small"
                class="admin-org-pill-btn-muted"
                @click="refreshInvitationCode"
              >
                <el-icon class="mr-1"><Refresh /></el-icon>
                {{ t('admin.refreshInvitationCode') }}
              </el-button>
              <el-tooltip
                :content="t('admin.shareInviteTitle')"
                placement="top"
              >
                <el-button
                  size="small"
                  type="primary"
                  class="admin-org-pill-btn"
                  @click="copyShareMessage"
                >
                  <el-icon class="mr-1"><Share /></el-icon>
                  {{ t('admin.copyShareMessage') }}
                </el-button>
              </el-tooltip>
            </div>
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
              <span class="min-w-0 break-words">{{ m.name || m.phone }}</span>
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
              class="flex flex-col gap-2 mt-2 sm:flex-row sm:items-center"
            >
              <el-select
                v-model="addManagerSelect"
                :placeholder="t('admin.setManager')"
                size="small"
                class="w-full min-w-0 sm:max-w-xs"
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
      <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:flex-wrap">
        <el-button
          class="admin-org-pill-btn-ghost w-full sm:w-auto"
          @click="close"
        >
          {{ t('common.close') }}
        </el-button>
        <el-button
          v-if="type === 'org' && orgId"
          type="danger"
          class="admin-org-pill-btn-danger w-full sm:w-auto"
          :loading="deleteLoading"
          @click="deleteOrganization"
        >
          <el-icon class="mr-1"><Delete /></el-icon>
          {{ t('admin.deleteOrganization') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.token-period-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.admin-org-dialog {
  width: min(92vw, 720px) !important;
  max-width: 100%;
}

.admin-org-pill-btn.el-button--primary {
  border-radius: 9999px;
  padding-left: 1rem;
  padding-right: 1rem;
  font-weight: 500;
}

.admin-org-pill-btn-muted.el-button {
  border-radius: 9999px;
  padding-left: 0.875rem;
  padding-right: 0.875rem;
  font-weight: 500;
}

.admin-org-pill-btn-ghost.el-button {
  border-radius: 9999px;
  padding-left: 1rem;
  padding-right: 1rem;
  font-weight: 500;
}

.admin-org-pill-btn-danger.el-button--danger {
  border-radius: 9999px;
  padding-left: 1rem;
  padding-right: 1rem;
  font-weight: 500;
}
</style>
