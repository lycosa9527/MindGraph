<script setup lang="ts">
/**
 * Admin Trend Chart Modal - Reusable chart + token cards for org/user
 * Used by Schools and Users tabs when clicking a row
 * For org type: also shows managers on the general tab
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'

import { Delete, Loading } from '@element-plus/icons-vue'

import type { Chart as ChartInstance } from 'chart.js'

import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { queryErrorMessage } from '@/composables/admin/useQueryErrorNotification'
import { useScopedAbort } from '@/composables/core/useScopedAbort'
import { useLanguage, useNotifications } from '@/composables'
import {
  fetchAdminOrganizationManagers,
  fetchAdminOrganizationUsers,
  fetchAdminStatsTrendsOrganization,
  fetchAdminStatsTrendsUser,
  fetchAdminTokenStats,
  useAddAdminOrganizationManager,
  useDeleteAdminOrganization,
  useRemoveAdminOrganizationManager,
  useUpdateAdminOrganization,
} from '@/composables/queries'
import {
  isUnlimitedMemberLimit,
  SCHOOL_TIER_LIMITS,
  normalizeSchoolTier,
  type SchoolTier,
} from '@/constants/schoolTier'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  ADMIN_TREND_CHART_MOUNT_DELAY_MS,
  ADMIN_TREND_DAYS_MAP,
  formatAdminTrendNumber,
  renderAdminTrendLineChart,
} from '@/composables/admin/useAdminTrendChart'
import {
  clearAdminMindBotOrgSession,
  getAdminMindBotOrgSession,
} from '@/composables/admin/useAdminMindBotConfig'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'

import AdminSchoolDifySettings from './AdminSchoolDifySettings.vue'
import AdminSchoolMindBotTab from './AdminSchoolMindBotTab.vue'
import AdminSchoolOrgGeneralTab from './AdminSchoolOrgGeneralTab.vue'
import AdminSchoolTokenUsageTab from './AdminSchoolTokenUsageTab.vue'

type SchoolDialogTab =
  | 'usage'
  | 'dify'
  | 'mindbot_dingtalk'
  | 'mindbot_log'
  | 'mindbot_monitor'
  | 'general'

const MIND_BOT_SCHOOL_TABS = new Set<SchoolDialogTab>([
  'mindbot_dingtalk',
  'mindbot_log',
  'mindbot_monitor',
])

const props = defineProps<{
  visible: boolean
  type: 'org' | 'user'
  initialSchoolTab?: SchoolDialogTab
  orgName?: string
  orgId?: number
  orgDisplayName?: string
  orgIsActive?: boolean
  orgUserCount?: number
  orgExpiresAt?: string | null
  orgSchoolTier?: string | null
  orgDifyApiBaseUrl?: string | null
  orgDifyApiKeyMasked?: string | null
  orgDifyTimeoutSeconds?: number
  orgDingtalkAiCardStreamingMaxChars?: number
  orgShowChainOfThought?: boolean
  orgMindmateAgentName?: string | null
  orgMindmateAgentAvatarUrl?: string | null
  userName?: string
  userId?: number
  readOnly?: boolean
  initialTrendPeriod?: 'today' | 'week' | 'month' | 'total'
  orgService?: 'mindgraph' | 'mindmate' | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'refresh'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const uiStore = useUIStore()
const { can } = useAdminAccess()
const { featureMindbot } = useFeatureFlags()
const { emit: emitAdminEvent } = useAdminEventBus('AdminTrendChartModal')
const { beginRequest: beginChartRequest, abort: abortChartRequests } = useScopedAbort()

const updateOrganizationMutation = useUpdateAdminOrganization()
const deleteOrganizationMutation = useDeleteAdminOrganization()
const addManagerMutation = useAddAdminOrganizationManager()
const removeManagerMutation = useRemoveAdminOrganizationManager()

const panelReadOnly = computed(() => props.readOnly === true)

const showMindbotSchoolTabs = computed(
  () => !panelReadOnly.value && can('tab.settings.mindbot') && featureMindbot.value
)

function isMindbotSchoolTab(tab: SchoolDialogTab): boolean {
  return MIND_BOT_SCHOOL_TABS.has(tab)
}

function mindbotEmbeddedPane(
  tab: SchoolDialogTab
): 'dingtalk' | 'log' | 'monitor' | null {
  if (tab === 'mindbot_dingtalk') {
    return 'dingtalk'
  }
  if (tab === 'mindbot_log') {
    return 'log'
  }
  if (tab === 'mindbot_monitor') {
    return 'monitor'
  }
  return null
}

const schoolDialogTab = ref<SchoolDialogTab>('usage')

const activeMindbotPane = computed(() => mindbotEmbeddedPane(schoolDialogTab.value))

const mindbotSaving = computed(() => {
  const orgId = props.orgId
  if (orgId == null || activeMindbotPane.value == null) {
    return false
  }
  return getAdminMindBotOrgSession(orgId).saving.value
})

const mindbotSaveEnabled = computed(() => {
  const orgId = props.orgId
  if (orgId == null) {
    return false
  }
  return !getAdminMindBotOrgSession(orgId).featureDisabled.value
})

const showMindbotFooterEnable = computed(
  () => isMindbotSchoolTab(schoolDialogTab.value) && props.orgId != null && mindbotSaveEnabled.value
)

const mindbotEnabled = computed({
  get: () => {
    const orgId = props.orgId
    if (orgId == null) {
      return false
    }
    return getAdminMindBotOrgSession(orgId).form.value.is_enabled
  },
  set: (enabled: boolean) => {
    const orgId = props.orgId
    if (orgId == null) {
      return
    }
    getAdminMindBotOrgSession(orgId).form.value.is_enabled = enabled
  },
})

async function saveMindbotSettings(): Promise<void> {
  const orgId = props.orgId
  if (orgId == null) {
    return
  }
  const saved = await getAdminMindBotOrgSession(orgId).saveConfig()
  if (saved) {
    emit('refresh')
  }
}

function clearMindbotSessionIfNeeded(): void {
  if (props.orgId != null) {
    clearAdminMindBotOrgSession(props.orgId)
  }
}

function onSchoolModalVisibleChange(visible: boolean): void {
  if (!visible) {
    clearMindbotSessionIfNeeded()
  }
  emit('update:visible', visible)
}

const chartTitle = ref('')
const chartLoading = ref(false)
const chartHasData = ref(true)
const chartRef = ref<HTMLCanvasElement | null>(null)
const tokenUsageTabRef = ref<InstanceType<typeof AdminSchoolTokenUsageTab> | null>(null)
const mindmateDifyRef = ref<InstanceType<typeof AdminSchoolDifySettings> | null>(null)
let chartInstance: ChartInstance<'line'> | null = null

const schoolHeaderNote = computed(() => {
  if (props.type !== 'org') {
    return props.orgName || '—'
  }
  const nick = (displayNameEdit.value || props.orgDisplayName || '').trim()
  const legal = (props.orgName ?? '').trim()
  if (nick && legal && nick !== legal) {
    return `${nick} · ${legal}`
  }
  return nick || legal || '—'
})

function chartCanvasElement(): HTMLCanvasElement | null {
  if (props.type === 'org') {
    return tokenUsageTabRef.value?.chartRef ?? null
  }
  return chartRef.value
}

const periodCards = ref({ today: '-', week: '-', month: '-', total: '-' })
const period = ref<'today' | 'week' | 'month' | 'total'>('week')

const managers = ref<{ id: number; phone: string; name: string }[]>([])
const orgUsers = ref<{ id: number; phone: string; name: string }[]>([])
const managersLoading = ref(false)
const pendingManagerIds = ref<number[]>([])
const addManagersLoading = ref(false)
const displayNameEdit = ref('')
const generalTabSaving = ref(false)
const orgActiveState = ref(true)
const lockLoading = ref(false)
const deleteLoading = ref(false)
const expiresAtEdit = ref<string | null>(null)
const schoolTierEdit = ref<SchoolTier>('trial')

const selectedTierLimits = computed(() => SCHOOL_TIER_LIMITS[schoolTierEdit.value])

const tierDowngradeBlocked = computed(() => {
  if (props.type !== 'org') {
    return false
  }
  const limits = selectedTierLimits.value
  const memberCount = props.orgUserCount ?? 0
  const managerCount = managers.value.length
  const memberOverLimit =
    !isUnlimitedMemberLimit(limits.memberLimit) && memberCount > limits.memberLimit
  return memberOverLimit || managerCount > limits.managerLimit
})

function parseExpiresAtToDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})/)
  return m ? m[1] : null
}

function close() {
  abortChartRequests()
  clearMindbotSessionIfNeeded()
  emit('update:visible', false)
}

function handleClose() {
  abortChartRequests()
  chartInstance?.destroy()
  chartInstance = null
}

async function loadOrgChart(signal: AbortSignal) {
  if (props.orgName == null) return
  const daysMap = ADMIN_TREND_DAYS_MAP
  const days = daysMap[period.value]
  const hourly = period.value === 'today'
  return fetchAdminStatsTrendsOrganization(
    {
      organization_id: props.orgId,
      organization_name: props.orgId == null ? props.orgName : undefined,
      days,
      hourly,
      service: props.orgService ?? undefined,
    },
    signal
  )
}

async function loadUserChart(signal: AbortSignal) {
  if (props.userId == null) return
  const daysMap = ADMIN_TREND_DAYS_MAP
  const days = daysMap[period.value]
  return fetchAdminStatsTrendsUser(
    {
      user_id: props.userId,
      days,
      hourly: period.value === 'today',
    },
    signal
  )
}

async function loadOrgTokenCards(signal: AbortSignal, orgId: number) {
  const data = await fetchAdminTokenStats(orgId, signal)
  const fmt = (p: { input_tokens?: number; output_tokens?: number }) => {
    const i = p?.input_tokens ?? 0
    const o = p?.output_tokens ?? 0
    return `${formatAdminTrendNumber(i)}+${formatAdminTrendNumber(o)}`
  }
  const service = props.orgService
  if (service === 'mindgraph' && data.by_service?.mindgraph) {
    const stats = data.by_service.mindgraph
    periodCards.value = {
      today: fmt(stats.today),
      week: fmt(stats.week),
      month: fmt(stats.month),
      total: fmt(stats.total),
    }
    return
  }
  if (service === 'mindmate' && data.by_service?.mindmate) {
    const stats = data.by_service.mindmate
    periodCards.value = {
      today: fmt(stats.today),
      week: fmt(stats.week),
      month: fmt(stats.month),
      total: fmt(stats.total),
    }
    return
  }
  periodCards.value = {
    today: fmt(data.today),
    week: fmt(data.past_week),
    month: fmt(data.past_month),
    total: fmt(data.total),
  }
}

async function loadUserTokenCards(signal: AbortSignal) {
  if (props.userId == null) return
  const data = await fetchAdminStatsTrendsUser({ user_id: props.userId, days: 0 }, signal)
  const arr = (data as { data?: Array<{ value?: number }> }).data ?? []
  const sum = (n: number) =>
    arr.slice(-n).reduce((a: number, b: { value?: number }) => a + (b.value ?? 0), 0)
  periodCards.value = {
    today: formatAdminTrendNumber(sum(1) || 0),
    week: formatAdminTrendNumber(sum(7) || 0),
    month: formatAdminTrendNumber(sum(30) || 0),
    total: formatAdminTrendNumber(arr.reduce((a: number, b: { value?: number }) => a + (b.value ?? 0), 0)),
  }
}

async function renderChart(data: {
  data: Array<{ date: string; value: number; input?: number; output?: number }>
}) {
  const canvas = chartCanvasElement()
  if (!canvas) return
  const rawData = data?.data ?? []
  const intlLocale = intlLocaleForUiCode(uiStore.language)
  const result = await renderAdminTrendLineChart({
    canvas,
    title: chartTitle.value,
    rawData,
    intlLocale,
    inputLabel: t('admin.inputTokens'),
    outputLabel: t('admin.outputTokens'),
    existingInstance: chartInstance,
  })
  chartInstance = result.instance
  chartHasData.value = result.hasData
}

async function load() {
  if (!props.visible) return
  if (props.type === 'org' && !props.orgName) return
  if (props.type === 'user' && props.userId == null) return
  chartLoading.value = true
  periodCards.value = { today: '-', week: '-', month: '-', total: '-' }
  const signal = beginChartRequest()
  try {
    if (props.type === 'org') {
      chartTitle.value = `${t('admin.trendOrgTokens')}: ${props.orgName ?? ''}`
      const data = await loadOrgChart(signal)
      const resolvedOrgId = props.orgId ?? data?.organization_id
      chartLoading.value = false
      await nextTick()
      await new Promise((r) => setTimeout(r, ADMIN_TREND_CHART_MOUNT_DELAY_MS))
      if (data) await renderChart({ data: data.data ?? [] })
      if (resolvedOrgId != null) {
        await loadOrgTokenCards(signal, resolvedOrgId)
      }
    } else {
      chartTitle.value = `${t('admin.trendUserTokens')}: ${props.userName ?? ''}`
      const data = await loadUserChart(signal)
      chartLoading.value = false
      await nextTick()
      await new Promise((r) => setTimeout(r, ADMIN_TREND_CHART_MOUNT_DELAY_MS))
      if (data) await renderChart({ data: data.data ?? [] })
      await loadUserTokenCards(signal)
    }
  } catch (err) {
    const message = queryErrorMessage(err, t('admin.dashboardLoadError'))
    if (message) {
      notify.error(message)
    }
    chartLoading.value = false
  }
}

async function switchPeriod(p: 'today' | 'week' | 'month' | 'total') {
  period.value = p
  await load()
}

async function loadManagersAndUsers() {
  if (props.type !== 'org' || props.orgId == null) return
  managersLoading.value = true
  try {
    const [managerRows, userRows] = await Promise.all([
      fetchAdminOrganizationManagers(props.orgId),
      fetchAdminOrganizationUsers(props.orgId),
    ])
    managers.value = managerRows.map((user) => ({
      id: user.id,
      phone: user.phone ?? '',
      name: user.name ?? user.phone ?? '',
    }))
    const managerIds = new Set(managers.value.map((x) => x.id))
    orgUsers.value = userRows
      .filter((user) => {
        const row = user as { id: number; is_manager?: boolean }
        return !managerIds.has(row.id) && !row.is_manager
      })
      .map((user) => ({
        id: user.id,
        phone: user.phone ?? '',
        name: user.name ?? user.phone ?? '',
      }))
  } catch {
    managers.value = []
    orgUsers.value = []
  } finally {
    managersLoading.value = false
  }
}

async function addManagers() {
  if (props.orgId == null || pendingManagerIds.value.length === 0) {
    return
  }
  const managerLimit = SCHOOL_TIER_LIMITS[schoolTierEdit.value].managerLimit
  const remaining = Math.max(0, managerLimit - managers.value.length)
  if (remaining === 0) {
    notify.warning(t('admin.schoolManagerLimitReached', { limit: managerLimit }))
    return
  }
  if (pendingManagerIds.value.length > remaining) {
    notify.warning(t('admin.schoolManagerLimitReached', { limit: managerLimit }))
    pendingManagerIds.value = pendingManagerIds.value.slice(0, remaining)
    return
  }
  const userIds = [...pendingManagerIds.value]
  addManagersLoading.value = true
  try {
    await Promise.all(
      userIds.map((userId) =>
        addManagerMutation.mutateAsync({ orgId: props.orgId as number, userId })
      )
    )
    notify.success(t('notification.saved'))
    pendingManagerIds.value = []
    await loadManagersAndUsers()
    emit('refresh')
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.trendChartErrors.setManagerFailed'))
    await loadManagersAndUsers()
  } finally {
    addManagersLoading.value = false
  }
}

async function removeManager(userId: number) {
  if (props.orgId == null) return
  try {
    await removeManagerMutation.mutateAsync({ orgId: props.orgId, userId })
    notify.success(t('notification.saved'))
    await loadManagersAndUsers()
    emit('refresh')
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.trendChartErrors.removeManagerFailed'))
  }
}

async function saveGeneralSettings() {
  if (props.orgId == null) {
    return
  }
  if (tierDowngradeBlocked.value) {
    const limits = selectedTierLimits.value
    notify.warning(
      t('admin.schoolTierDowngradeBlocked', {
        members: props.orgUserCount ?? 0,
        memberLimit: isUnlimitedMemberLimit(limits.memberLimit)
          ? t('admin.unlimited')
          : limits.memberLimit,
        managers: managers.value.length,
        managerLimit: limits.managerLimit <= 0
          ? t('admin.noSchoolManagersShort')
          : limits.managerLimit,
      })
    )
    return
  }
  generalTabSaving.value = true
  try {
    const dateVal = expiresAtEdit.value?.trim() || null
    const expiresAtPayload = dateVal ? `${dateVal}T23:59:59+08:00` : null
    const updated = await updateOrganizationMutation.mutateAsync({
      orgId: props.orgId,
      body: {
        display_name: displayNameEdit.value.trim() || null,
        expires_at: expiresAtPayload,
        school_tier: schoolTierEdit.value,
      },
    })
    const savedTier = updated.school_tier
    if (typeof savedTier === 'string' && savedTier.trim()) {
      schoolTierEdit.value = normalizeSchoolTier(savedTier)
    }
    notify.success(t('notification.saved'))
    emit('refresh')
    emitAdminEvent('admin:mutation_completed', {
      domain: 'organizations',
      entityId: props.orgId,
    })
    const savedLabel = displayNameEdit.value.trim()
    if (authStore.user?.schoolId === String(props.orgId)) {
      authStore.patchSchoolDisplayName(savedLabel || null, props.orgName)
      void authStore.refreshUserProfile({ bypassThrottle: true })
    }
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.trendChartErrors.saveFailed'))
  } finally {
    generalTabSaving.value = false
  }
}

async function toggleLock() {
  if (props.orgId == null) return
  lockLoading.value = true
  try {
    const newActive = !orgActiveState.value
    await updateOrganizationMutation.mutateAsync({
      orgId: props.orgId,
      body: { is_active: newActive },
    })
    orgActiveState.value = newActive
    notify.success(t('notification.saved'))
    emit('refresh')
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.trendChartErrors.updateFailed'))
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
    await deleteOrganizationMutation.mutateAsync({
      orgId: props.orgId,
      deleteUsers: userCount > 0,
    })
    notify.success(t('notification.saved'))
    emit('update:visible', false)
    emit('refresh')
  } catch (err) {
    const detail = err instanceof Error ? err.message : ''
    notify.error(detail || t('admin.trendChartErrors.deleteOrgFailed'))
  } finally {
    deleteLoading.value = false
  }
}

function loadGeneralTabData() {
  if (props.type !== 'org' || props.orgId == null) {
    return
  }
  void loadManagersAndUsers()
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      period.value = props.initialTrendPeriod ?? 'week'
      if (props.type === 'org') {
        schoolDialogTab.value = props.initialSchoolTab ?? 'usage'
      }
      void load()
      if (props.type === 'org' && props.orgId) {
        displayNameEdit.value = props.orgDisplayName ?? ''
        orgActiveState.value = props.orgIsActive ?? true
        expiresAtEdit.value = parseExpiresAtToDate(props.orgExpiresAt)
        schoolTierEdit.value = normalizeSchoolTier(props.orgSchoolTier)
        loadGeneralTabData()
      }
    } else {
      abortChartRequests()
      chartInstance?.destroy()
      chartInstance = null
      pendingManagerIds.value = []
    }
  }
)

watch(
  () => props.orgDisplayName,
  (name) => {
    if (props.visible && props.type === 'org') {
      displayNameEdit.value = name ?? ''
    }
  }
)

watch(schoolDialogTab, (tab) => {
  if (tab === 'general' && props.visible && props.type === 'org' && props.orgId) {
    loadGeneralTabData()
  }
})

watch(
  () =>
    [
      props.orgId,
      props.orgName,
      props.orgDisplayName,
      props.orgIsActive,
      props.orgExpiresAt,
      props.orgSchoolTier,
      props.userId,
      props.userName,
    ] as const,
  () => {
    if (!props.visible) {
      return
    }
    void load()
    if (props.type === 'org' && props.orgId) {
      displayNameEdit.value = props.orgDisplayName ?? ''
      orgActiveState.value = props.orgIsActive ?? true
      expiresAtEdit.value = parseExpiresAtToDate(props.orgExpiresAt)
      schoolTierEdit.value = normalizeSchoolTier(props.orgSchoolTier)
      if (schoolDialogTab.value === 'general') {
        loadGeneralTabData()
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
    v-if="type === 'org'"
    :model-value="visible"
    class="school-settings-dialog mindbot-settings-dialog mindbot-swiss-dialog"
    width="min(760px, 94vw)"
    destroy-on-close
    append-to-body
    align-center
    modal-class="mindbot-swiss-backdrop"
    :show-close="true"
    @update:model-value="onSchoolModalVisibleChange"
    @close="handleClose"
  >
    <template #header>
      <div class="mindbot-swiss-header mindbot-config-header">
        <span class="mindbot-swiss-header__glyph">◇</span>
        <span class="mindbot-swiss-header__title">{{ t('admin.editSchool') }}</span>
        <span
          class="mindbot-swiss-header__divider"
          aria-hidden="true"
          >·</span
        >
        <span class="mindbot-swiss-header__note">{{ schoolHeaderNote }}</span>
      </div>
    </template>
    <div class="mindbot-config-body">
      <div
        class="mindbot-config-scanlines"
        aria-hidden="true"
      />
      <div class="mindbot-swiss-form-wrap">
        <el-tabs
          v-model="schoolDialogTab"
          class="mindbot-dialog-tabs school-dialog-tabs"
        >
          <el-tab-pane
            name="usage"
            :label="t('admin.schoolModal.tabUsage')"
          >
            <AdminSchoolTokenUsageTab
              ref="tokenUsageTabRef"
              :chart-loading="chartLoading"
              :period="period"
              :period-cards="periodCards"
              @switchPeriod="switchPeriod"
            />
          </el-tab-pane>
          <el-tab-pane
            name="dify"
            :label="t('admin.schoolModal.tabMindmate')"
            lazy
          >
            <AdminSchoolDifySettings
              v-if="orgId"
              ref="mindmateDifyRef"
              :org-id="orgId"
              :dify-api-base-url="orgDifyApiBaseUrl"
              :dify-api-key-masked="orgDifyApiKeyMasked"
              :dify-timeout-seconds="orgDifyTimeoutSeconds"
              :dingtalk-ai-card-streaming-max-chars="orgDingtalkAiCardStreamingMaxChars"
              :show-chain-of-thought="orgShowChainOfThought"
              :mindmate-agent-name="orgMindmateAgentName"
              :mindmate-agent-avatar-url="orgMindmateAgentAvatarUrl"
              @saved="emit('refresh')"
            />
          </el-tab-pane>
          <el-tab-pane
            v-if="showMindbotSchoolTabs"
            name="mindbot_dingtalk"
            :label="t('admin.mindbot.tabDingtalk')"
            lazy
          >
            <AdminSchoolMindBotTab
              v-if="orgId && schoolDialogTab === 'mindbot_dingtalk'"
              :org-id="orgId"
              embedded-pane="dingtalk"
              :active="true"
              @refresh="emit('refresh')"
            />
          </el-tab-pane>
          <el-tab-pane
            v-if="showMindbotSchoolTabs"
            name="mindbot_log"
            :label="t('admin.mindbot.tabLog')"
            lazy
          >
            <AdminSchoolMindBotTab
              v-if="orgId && schoolDialogTab === 'mindbot_log'"
              :org-id="orgId"
              embedded-pane="log"
              :active="true"
            />
          </el-tab-pane>
          <el-tab-pane
            v-if="showMindbotSchoolTabs"
            name="mindbot_monitor"
            :label="t('admin.mindbot.tabMonitor')"
            lazy
          >
            <AdminSchoolMindBotTab
              v-if="orgId && schoolDialogTab === 'mindbot_monitor'"
              :org-id="orgId"
              embedded-pane="monitor"
              :active="true"
            />
          </el-tab-pane>
          <el-tab-pane
            name="general"
            :label="t('admin.schoolModal.tabGeneral')"
            lazy
          >
            <AdminSchoolOrgGeneralTab
              v-if="orgId"
              v-model:display-name-edit="displayNameEdit"
              v-model:expires-at-edit="expiresAtEdit"
              v-model:school-tier-edit="schoolTierEdit"
              v-model:pending-manager-ids="pendingManagerIds"
              :org-name="orgName"
              :org-active-state="orgActiveState"
              :org-user-count="orgUserCount"
              :managers="managers"
              :org-users="orgUsers"
              :managers-loading="managersLoading"
              :add-managers-loading="addManagersLoading"
              :lock-loading="lockLoading"
              :read-only="panelReadOnly"
              @toggleLock="toggleLock"
              @addManagers="addManagers"
              @removeManager="removeManager"
            />
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
    <template #footer>
      <div
        class="mindbot-dialog-footer flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
      >
        <div
          v-if="showMindbotFooterEnable && !panelReadOnly"
          class="mindbot-footer-enable flex min-w-0 items-center gap-2 sm:gap-2.5 order-last sm:order-first"
        >
          <span class="mindbot-footer-enable__label">{{ t('admin.mindbot.enabled') }}</span>
          <el-switch
            v-model="mindbotEnabled"
            class="mindbot-footer-enabled-switch shrink-0"
          />
        </div>
        <div
          v-if="!panelReadOnly"
          class="flex shrink-0 flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end sm:flex-wrap sm:ml-auto"
        >
        <el-button
          v-if="schoolDialogTab === 'general' && orgId"
          type="primary"
          class="mindbot-pill mindbot-pill--footer-save w-full sm:w-auto"
          :loading="generalTabSaving"
          :disabled="tierDowngradeBlocked"
          @click="saveGeneralSettings"
        >
          {{ t('admin.save') }}
        </el-button>
        <el-tooltip
          v-else-if="schoolDialogTab === 'dify' && orgId"
          :disabled="Boolean(mindmateDifyRef?.canSave)"
          :content="t('admin.schoolDifyAuthRequiredBeforeSave')"
          placement="top"
        >
          <el-button
            type="primary"
            class="mindbot-pill mindbot-pill--footer-save w-full sm:w-auto"
            :loading="mindmateDifyRef?.saving"
            :disabled="!mindmateDifyRef?.canSave"
            @click="mindmateDifyRef?.saveSettings()"
          >
            {{ t('admin.save') }}
          </el-button>
        </el-tooltip>
        <el-button
          v-else-if="isMindbotSchoolTab(schoolDialogTab) && orgId && mindbotSaveEnabled"
          type="primary"
          class="mindbot-pill mindbot-pill--footer-save w-full sm:w-auto"
          :loading="mindbotSaving"
          @click="saveMindbotSettings()"
        >
          {{ t('admin.mindbot.save') }}
        </el-button>
        <el-button
          class="mindbot-pill mindbot-pill--footer-cancel w-full sm:w-auto"
          @click="close"
        >
          {{ t('common.close') }}
        </el-button>
        <el-button
          v-if="orgId"
          type="danger"
          plain
          class="mindbot-pill mindbot-pill--footer-danger w-full sm:w-auto"
          :loading="deleteLoading"
          @click="deleteOrganization"
        >
          <el-icon class="mr-1"><Delete /></el-icon>
          {{ t('admin.deleteOrganization') }}
        </el-button>
        </div>
      </div>
    </template>
  </el-dialog>

  <el-dialog
    v-else
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
      <div
        v-if="!chartHasData"
        class="flex justify-center items-center h-64 text-gray-500 dark:text-gray-400"
      >
        {{ t('admin.trendChartNoData') }}
      </div>
      <div
        v-else
        class="relative h-64 min-h-[220px] sm:min-h-[256px] w-full min-w-0"
      >
        <canvas
          ref="chartRef"
          class="block w-full h-full"
        />
      </div>
      <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div class="grid grid-cols-1 min-[400px]:grid-cols-2 lg:grid-cols-4 gap-3">
          <AdminSwissPeriodCard
            :label="t('admin.today')"
            :value="periodCards.today"
            :active="period === 'today'"
            theme="storage"
            @click="switchPeriod('today')"
          />
          <AdminSwissPeriodCard
            :label="t('admin.pastWeek')"
            :value="periodCards.week"
            :active="period === 'week'"
            theme="storage"
            @click="switchPeriod('week')"
          />
          <AdminSwissPeriodCard
            :label="t('admin.pastMonth')"
            :value="periodCards.month"
            :active="period === 'month'"
            theme="storage"
            @click="switchPeriod('month')"
          />
          <AdminSwissPeriodCard
            :label="t('admin.allTime')"
            :value="periodCards.total"
            :active="period === 'total'"
            theme="storage"
            @click="switchPeriod('total')"
          />
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
      </div>
    </template>
  </el-dialog>
</template>

<style>
@import '@/styles/admin-mindbot-swiss-dialog-chrome.css';
</style>

<style scoped>
.school-settings-dialog.mindbot-swiss-dialog {
  width: min(92vw, 800px) !important;
  max-width: 100%;
  border-radius: 2px;
  overflow: hidden;
}

.school-dialog-tabs :deep(.el-tabs__content) {
  padding-top: 12px;
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

.admin-org-pill-btn-ghost.el-button {
  border-radius: 9999px;
  padding-left: 1rem;
  padding-right: 1rem;
  font-weight: 500;
}

.mindbot-footer-enable__label {
  font-family: var(--geek-ulog-font);
  font-weight: 600;
  font-size: 0.6875rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #e2e8f0;
  line-height: 1.35;
}

.mindbot-footer-enabled-switch.el-switch {
  --el-switch-on-color: #22d3ee;
}
</style>
