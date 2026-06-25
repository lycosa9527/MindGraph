<script setup lang="ts">
/**
 * MindMate 记录导出 — view + export Dify conversation history.
 *
 * Superadmin-only panel: pick any org. Conversations are merged across both
 * Dify servers (each row shows its source server). The transcript viewer
 * renders WeChat/Telegram-style bubbles; downloads stream as HTML / JSON / ZIP.
 */
import { computed, ref, watch } from 'vue'

import AdminMindMateExportDumpsTab from '@/components/admin/AdminMindMateExportDumpsTab.vue'
import { useMindMateExportPanelTab } from '@/composables/admin/useMindMateExportPanelTab'
import { useLanguage, useNotifications } from '@/composables'
import { useMindMateExportJobStream } from '@/composables/admin/useMindMateExportJobStream'
import {
  cancelMindMateExportJob,
  createMindMateExportJob,
  downloadMindMateExport,
  downloadMindMateExportJob,
  fetchMindMateExportConversations,
  fetchMindMateExportMessages,
  pauseMindMateExportJob,
  resumeMindMateExportJob,
  useAdminOrganizations,
  useMindMateExportConversations,
  useMindMateExportUsers,
  type MindMateExportBubble,
  type MindMateExportConversation,
  type MindMateExportFilters,
  type MindMateExportJob,
} from '@/composables/queries'

const { t } = useLanguage()
const notify = useNotifications()

type ExportFormat = 'html' | 'json' | 'zip'
type ScopeMode = 'all' | 'whole' | 'users'
type DatePreset = 'today' | 'week' | 'month' | 'year' | 'all'

const selectedOrgId = ref<number | null>(null)
const scopeMode = ref<ScopeMode>('all')
const selectedUserIds = ref<number[]>([])
const dateRange = ref<[Date, Date] | null>(null)
const activeDatePreset = ref<DatePreset | null>(null)
const datePickerKey = ref(0)
const exportFormat = ref<ExportFormat>('html')
const { panelTab } = useMindMateExportPanelTab()

const dateTimeDefaultRange: [Date, Date] = [
  new Date(2000, 0, 1, 0, 0, 0),
  new Date(2000, 0, 1, 0, 0, 0),
]

const scopeOptions = computed(() => [
  { label: t('admin.mindmateExport.scopeAll'), value: 'all' as ScopeMode },
  { label: t('admin.mindmateExport.scopeWholeOrg'), value: 'whole' as ScopeMode },
  { label: t('admin.mindmateExport.scopeUsers'), value: 'users' as ScopeMode },
])

const formatOptions = computed(() => [
  { label: t('admin.mindmateExport.formatHtml'), value: 'html' as ExportFormat },
  { label: t('admin.mindmateExport.formatJson'), value: 'json' as ExportFormat },
  { label: t('admin.mindmateExport.formatZip'), value: 'zip' as ExportFormat },
])

const datePresetOptions = computed(() => [
  { id: 'today' as const, label: t('admin.today') },
  { id: 'week' as const, label: t('admin.thisWeek') },
  { id: 'month' as const, label: t('admin.thisMonth') },
  { id: 'year' as const, label: t('admin.thisYear') },
  { id: 'all' as const, label: t('admin.allTime') },
])

// ---------------------------------------------------------------------------
// Organizations (superadmin) + users
// ---------------------------------------------------------------------------
const orgsQuery = useAdminOrganizations()
const orgOptions = computed(() =>
  (orgsQuery.data.value ?? []).map((org) => ({
    label: `${org.name} (${org.code})`,
    value: org.id,
  }))
)
const orgNameById = computed(() => {
  const map = new Map<number, string>()
  for (const org of orgsQuery.data.value ?? []) {
    map.set(org.id, org.name)
  }
  return map
})
const usersQuery = useMindMateExportUsers(selectedOrgId, {
  enabled: computed(() => selectedOrgId.value != null),
})
const userOptions = computed(() =>
  (usersQuery.data.value?.users ?? []).map((u) => ({ label: u.label, value: u.id }))
)

watch(selectedOrgId, () => {
  selectedUserIds.value = []
  appliedFilters.value = null
  activeConversation.value = null
  resetListState()
})

watch(scopeMode, (mode) => {
  if (mode === 'all') {
    selectedOrgId.value = null
    selectedUserIds.value = []
  }
  appliedFilters.value = null
  activeConversation.value = null
  resetListState()
})

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------
function startOfDay(value: Date): Date {
  const day = new Date(value)
  day.setHours(0, 0, 0, 0)
  return day
}

function endOfDay(value: Date): Date {
  const day = new Date(value)
  day.setHours(23, 59, 59, 999)
  return day
}

function isMidnight(value: Date): boolean {
  return (
    value.getHours() === 0 &&
    value.getMinutes() === 0 &&
    value.getSeconds() === 0 &&
    value.getMilliseconds() === 0
  )
}

/** Date-only picks (00:00 default time) span full calendar days; explicit times are kept. */
function normalizeExportRange(from: Date, to: Date): { start: Date; end: Date } {
  return {
    start: isMidnight(from) ? startOfDay(from) : new Date(from.getTime()),
    end: isMidnight(to) ? endOfDay(to) : new Date(to.getTime()),
  }
}

function rangeEpoch(): { start: number | null; end: number | null } {
  if (!dateRange.value) {
    return { start: null, end: null }
  }
  const [from, to] = dateRange.value
  if (!from || !to) {
    return { start: null, end: null }
  }
  const { start, end } = normalizeExportRange(from, to)
  return {
    start: Math.floor(start.getTime() / 1000),
    end: Math.floor(end.getTime() / 1000),
  }
}

function startOfWeekMonday(value: Date): Date {
  const day = startOfDay(value)
  const weekday = day.getDay()
  const daysFromMonday = weekday === 0 ? 6 : weekday - 1
  day.setDate(day.getDate() - daysFromMonday)
  return day
}

function rangeForPreset(preset: Exclude<DatePreset, 'all'>): [Date, Date] {
  const now = new Date()
  if (preset === 'today') {
    return [startOfDay(now), now]
  }
  if (preset === 'week') {
    return [startOfWeekMonday(now), now]
  }
  if (preset === 'month') {
    return [new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0), now]
  }
  return [new Date(now.getFullYear(), 0, 1, 0, 0, 0, 0), now]
}

function applyDatePreset(preset: DatePreset): void {
  suppressDatePickerChange = true
  activeDatePreset.value = preset
  if (preset === 'all') {
    dateRange.value = null
  } else {
    const [start, end] = rangeForPreset(preset)
    dateRange.value = [new Date(start.getTime()), new Date(end.getTime())]
  }
  datePickerKey.value += 1
  queueMicrotask(() => {
    suppressDatePickerChange = false
  })
}

let suppressDatePickerChange = false

function onDateRangePickerChange(): void {
  if (suppressDatePickerChange) {
    return
  }
  activeDatePreset.value = null
}

const appliedFilters = ref<MindMateExportFilters | null>(null)
const accumulatedConversations = ref<MindMateExportConversation[]>([])
const listNextCursor = ref<string | null>(null)
const listHasMore = ref(false)
const requiresJob = ref(false)
const listVerificationStatus = ref<string | null>(null)
const listStats = ref({
  usersTotal: 0,
  usersScanned: 0,
  targetsCount: 0,
  conversationsTotal: 0,
  partialFailures: 0,
})
const loadingMore = ref(false)
const exportWarnings = ref<string[]>([])
const downloadVerificationStatus = ref<string | null>(null)

function resetListState(): void {
  accumulatedConversations.value = []
  listNextCursor.value = null
  listHasMore.value = false
  requiresJob.value = false
  listVerificationStatus.value = null
  downloadVerificationStatus.value = null
  exportWarnings.value = []
  listStats.value = {
    usersTotal: 0,
    usersScanned: 0,
    targetsCount: 0,
    conversationsTotal: 0,
    partialFailures: 0,
  }
}

const conversationsQuery = useMindMateExportConversations(
  () => appliedFilters.value ?? {},
  { enabled: computed(() => appliedFilters.value != null) }
)

const conversations = computed<MindMateExportConversation[]>(() => accumulatedConversations.value)
const hasLoadedConversations = computed(() => appliedFilters.value != null)
const loadingConversations = computed(
  () => appliedFilters.value != null && conversationsQuery.isFetching.value && !loadingMore.value
)

watch(
  () => conversationsQuery.data.value,
  (data) => {
    if (!data || appliedFilters.value == null) {
      return
    }
    accumulatedConversations.value = data.conversations
    listNextCursor.value = data.next_cursor
    listHasMore.value = data.has_more
    requiresJob.value = data.requires_job
    listVerificationStatus.value = data.verification_status
    exportWarnings.value = data.warnings
    listStats.value = {
      usersTotal: data.users_total,
      usersScanned: data.users_scanned,
      targetsCount: data.targets_count,
      conversationsTotal: data.conversations_total,
      partialFailures: data.partial_failures,
    }
  }
)

function currentFilters(): MindMateExportFilters | null {
  if (scopeMode.value !== 'all' && selectedOrgId.value == null) {
    notify.error(t('admin.mindmateExport.selectOrgFirst'))
    return null
  }
  if (scopeMode.value === 'users' && selectedUserIds.value.length === 0) {
    notify.error(t('admin.mindmateExport.selectUsersFirst'))
    return null
  }
  const { start, end } = rangeEpoch()
  return {
    scope: scopeMode.value,
    orgId: scopeMode.value === 'all' ? null : selectedOrgId.value,
    userIds: scopeMode.value === 'users' ? selectedUserIds.value : [],
    start,
    end,
  }
}

function loadConversations(): void {
  const filters = currentFilters()
  if (!filters) {
    return
  }
  activeConversation.value = null
  resetListState()
  activeJobId.value = null
  appliedFilters.value = filters
}

async function loadMoreConversations(): Promise<void> {
  if (!appliedFilters.value || !listNextCursor.value || loadingMore.value) {
    return
  }
  loadingMore.value = true
  try {
    const res = await fetchMindMateExportConversations({
      ...appliedFilters.value,
      cursor: listNextCursor.value,
    })
    accumulatedConversations.value = [...accumulatedConversations.value, ...res.conversations]
    listNextCursor.value = res.next_cursor
    listHasMore.value = res.has_more
  } catch {
    notify.error(t('admin.mindmateExport.loadError'))
  } finally {
    loadingMore.value = false
  }
}

watch(
  () => conversationsQuery.error.value,
  (err) => {
    if (err) {
      notify.error(t('admin.mindmateExport.loadError'))
    }
  }
)

// ---------------------------------------------------------------------------
// Transcript viewer
// ---------------------------------------------------------------------------
const activeConversation = ref<MindMateExportConversation | null>(null)
const bubbles = ref<MindMateExportBubble[]>([])
const loadingBubbles = ref(false)

async function openTranscript(conversation: MindMateExportConversation): Promise<void> {
  activeConversation.value = conversation
  bubbles.value = []
  loadingBubbles.value = true
  try {
    const res = await fetchMindMateExportMessages(conversation.conversation_id, {
      server: conversation.server,
      difyUser: conversation.dify_user,
      orgId: conversation.organization_id,
      channel: conversation.channel,
      mindbotConfigId: conversation.mindbot_config_id,
    })
    bubbles.value = res.bubbles
  } catch {
    notify.error(t('admin.mindmateExport.loadError'))
  } finally {
    loadingBubbles.value = false
  }
}

function formatTime(epoch: number): string {
  if (!epoch) {
    return ''
  }
  return new Date(epoch * 1000).toLocaleString()
}

function bubbleRoleLabel(role: string): string {
  return role === 'user'
    ? t('admin.mindmateExport.roleUser')
    : t('admin.mindmateExport.roleAssistant')
}

function channelLabel(channel: string): string {
  return channel === 'mindbot'
    ? t('admin.mindmateExport.channelMindbot')
    : t('admin.mindmateExport.channelWeb')
}

function chatScopeLabel(scope: string | null | undefined): string | null {
  if (!scope) {
    return null
  }
  const normalized = scope.trim().toLowerCase()
  if (normalized === 'group') {
    return t('admin.mindmateExport.chatScopeGroup')
  }
  if (normalized === 'cross_org_group') {
    return t('admin.mindmateExport.chatScopeCrossOrg')
  }
  if (normalized === 'oto' || normalized === '1:1') {
    return t('admin.mindmateExport.chatScopeOto')
  }
  return scope
}

function chatScopeClass(scope: string | null | undefined): string {
  if (!scope) {
    return ''
  }
  const normalized = scope.trim().toLowerCase()
  if (normalized === 'cross_org_group') {
    return 'is-cross-org'
  }
  if (normalized === 'group') {
    return 'is-group'
  }
  if (normalized === 'oto' || normalized === '1:1') {
    return 'is-oto'
  }
  return 'is-group'
}

function conversationKey(conv: MindMateExportConversation): string {
  return `${conv.organization_id}:${conv.server}:${conv.dify_user}:${conv.conversation_id}`
}

// ---------------------------------------------------------------------------
// Export jobs
// ---------------------------------------------------------------------------
const activeJobId = ref<number | null>(null)
const jobActionPending = ref(false)
const { job: streamedJob } = useMindMateExportJobStream(activeJobId)

const activeJob = computed<MindMateExportJob | null>(() => streamedJob.value)
const showJobPanel = computed(
  () => activeJobId.value != null || (hasLoadedConversations.value && requiresJob.value)
)

const jobIsTerminal = computed(() => {
  const status = activeJob.value?.status
  return (
    status === 'completed'
    || status === 'completed_with_gaps'
    || status === 'cancelled'
    || status === 'failed'
    || status === 'failed_verification'
  )
})

const jobCanDownload = computed(() => {
  const status = activeJob.value?.status
  return status === 'completed' || status === 'completed_with_gaps'
})

const exportDataSourceSummary = computed((): string | null => {
  const report = activeJob.value?.verification_report as {
    actual?: { data_source?: { per_label?: Record<string, string> } }
  } | null
  const perLabel = report?.actual?.data_source?.per_label
  if (!perLabel || Object.keys(perLabel).length === 0) {
    return null
  }
  return Object.entries(perLabel)
    .map(([label, mode]) => `${label}: ${mode}`)
    .join(' · ')
})

function verificationBadgeLabel(status: string | null | undefined): string {
  if (status === 'pass' || status === 'completed') {
    return t('admin.mindmateExport.verifyPass')
  }
  if (status === 'gaps' || status === 'completed_with_gaps') {
    return t('admin.mindmateExport.verifyGaps')
  }
  return t('admin.mindmateExport.verifyFail')
}

function verificationBadgeClass(status: string | null | undefined): string {
  if (status === 'pass' || status === 'completed') {
    return 'is-pass'
  }
  if (status === 'gaps' || status === 'completed_with_gaps') {
    return 'is-gaps'
  }
  return 'is-fail'
}

function displayVerificationStatus(): string | null {
  return downloadVerificationStatus.value ?? listVerificationStatus.value
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function startExportJob(): Promise<void> {
  if (appliedFilters.value == null) {
    notify.error(t('admin.mindmateExport.loadPrompt'))
    return
  }
  downloading.value = true
  try {
    const orgName =
      appliedFilters.value.orgId != null
        ? orgLabel(appliedFilters.value.orgId)
        : undefined
    const res = await createMindMateExportJob(
      appliedFilters.value,
      exportFormat.value,
      orgName
    )
    activeJobId.value = res.job.id
    notify.success(t('admin.mindmateExport.jobProgress', {
      percent: res.job.progress_percent,
      stage: res.job.current_stage ?? res.job.status,
    }))
  } catch {
    notify.error(t('admin.mindmateExport.downloadError'))
  } finally {
    downloading.value = false
  }
}

async function pauseJob(): Promise<void> {
  if (activeJobId.value == null) {
    return
  }
  jobActionPending.value = true
  try {
    await pauseMindMateExportJob(activeJobId.value)
  } catch {
    notify.error(t('admin.mindmateExport.downloadError'))
  } finally {
    jobActionPending.value = false
  }
}

async function resumeJob(): Promise<void> {
  if (activeJobId.value == null) {
    return
  }
  jobActionPending.value = true
  try {
    await resumeMindMateExportJob(activeJobId.value)
  } catch {
    notify.error(t('admin.mindmateExport.downloadError'))
  } finally {
    jobActionPending.value = false
  }
}

async function cancelJob(): Promise<void> {
  if (activeJobId.value == null) {
    return
  }
  jobActionPending.value = true
  try {
    await cancelMindMateExportJob(activeJobId.value)
  } catch {
    notify.error(t('admin.mindmateExport.downloadError'))
  } finally {
    jobActionPending.value = false
  }
}

async function downloadJobArtifact(): Promise<void> {
  if (activeJobId.value == null) {
    return
  }
  downloading.value = true
  try {
    const { blob, filename, verification } = await downloadMindMateExportJob(activeJobId.value)
    downloadVerificationStatus.value = verification || activeJob.value?.status || null
    triggerBrowserDownload(blob, filename)
    notify.success(t('admin.mindmateExport.downloadSuccess'))
  } catch {
    notify.error(t('admin.mindmateExport.downloadError'))
  } finally {
    downloading.value = false
  }
}

// ---------------------------------------------------------------------------
// Download
// ---------------------------------------------------------------------------
const downloading = ref(false)

function orgLabel(orgId: number): string {
  return orgNameById.value.get(orgId) ?? `Org ${orgId}`
}

async function download(): Promise<void> {
  if (appliedFilters.value == null) {
    notify.error(t('admin.mindmateExport.loadPrompt'))
    return
  }
  if (requiresJob.value) {
    await startExportJob()
    return
  }
  downloading.value = true
  try {
    const { blob, filename, verification } = await downloadMindMateExport(
      appliedFilters.value,
      exportFormat.value
    )
    downloadVerificationStatus.value = verification || null
    triggerBrowserDownload(blob, filename)
    notify.success(t('admin.mindmateExport.downloadSuccess'))
  } catch {
    notify.error(t('admin.mindmateExport.downloadError'))
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <div class="mindmate-export-page">
    <template v-if="panelTab === 'export'">
    <p class="mindmate-export-privacy">
      {{ t('admin.mindmateExport.privacyNotice') }}
    </p>

    <section class="mindmate-export-card mindmate-export-filters">
      <div class="mindmate-export-filter-grid">
        <div class="mindmate-export-field mindmate-export-field--org">
          <label class="mindmate-export-label">{{ t('admin.mindmateExport.orgLabel') }}</label>
          <el-select
            v-model="selectedOrgId"
            filterable
            clearable
            :disabled="scopeMode === 'all'"
            :placeholder="
              scopeMode === 'all'
                ? t('admin.mindmateExport.orgAllSchools')
                : t('admin.mindmateExport.orgPlaceholder')
            "
            class="admin-swiss-select mindmate-export-select--org"
          >
            <el-option
              v-for="opt in orgOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </div>

        <div class="mindmate-export-field">
          <label class="mindmate-export-label">{{ t('admin.mindmateExport.scopeLabel') }}</label>
          <div
            class="admin-swiss-segmented admin-swiss-segmented--block"
            role="radiogroup"
            :aria-label="t('admin.mindmateExport.scopeLabel')"
          >
            <button
              v-for="opt in scopeOptions"
              :key="opt.value"
              type="button"
              role="radio"
              class="admin-swiss-segment"
              :class="{ 'is-active': scopeMode === opt.value }"
              :aria-checked="scopeMode === opt.value"
              @click="scopeMode = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div
          v-if="scopeMode === 'users'"
          class="mindmate-export-field mindmate-export-field--users"
        >
          <label class="mindmate-export-label">{{ t('admin.mindmateExport.usersLabel') }}</label>
          <el-select
            v-model="selectedUserIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            :placeholder="t('admin.mindmateExport.usersPlaceholder')"
            :loading="usersQuery.isFetching.value"
            class="admin-swiss-select mindmate-export-select--users"
          >
            <el-option
              v-for="opt in userOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </div>

        <div class="mindmate-export-field mindmate-export-field--dates">
          <div class="mindmate-export-dates-toolbar">
            <label class="mindmate-export-label">{{ t('admin.mindmateExport.dateRangeLabel') }}</label>
            <div
              class="mindmate-export-presets"
              role="group"
              :aria-label="t('admin.mindmateExport.dateRangeLabel')"
            >
              <button
                v-for="preset in datePresetOptions"
                :key="preset.id"
                type="button"
                class="mindmate-export-preset"
                :class="{ 'is-active': activeDatePreset === preset.id }"
                @click="applyDatePreset(preset.id)"
              >
                {{ preset.label }}
              </button>
            </div>
          </div>
          <el-date-picker
            :key="datePickerKey"
            v-model="dateRange"
            type="datetimerange"
            format="YYYY-MM-DD HH:mm"
            :default-time="dateTimeDefaultRange"
            :start-placeholder="t('admin.mindmateExport.startDateTime')"
            :end-placeholder="t('admin.mindmateExport.endDateTime')"
            clearable
            class="mindmate-export-date"
            @change="onDateRangePickerChange"
          />
          <p class="mindmate-export-dates-hint">
            {{ t('admin.mindmateExport.dateTimeHint') }}
          </p>
        </div>
      </div>

      <div class="mindmate-export-actions">
        <el-button
          type="primary"
          class="admin-swiss-btn admin-swiss-btn--primary"
          :loading="loadingConversations"
          @click="loadConversations"
        >
          {{ t('admin.mindmateExport.loadConversations') }}
        </el-button>
        <div class="mindmate-export-format">
          <span class="mindmate-export-label mindmate-export-label--inline">
            {{ t('admin.mindmateExport.formatLabel') }}
          </span>
          <div
            class="admin-swiss-segmented admin-swiss-segmented--equal"
            role="radiogroup"
            :aria-label="t('admin.mindmateExport.formatLabel')"
          >
            <button
              v-for="opt in formatOptions"
              :key="opt.value"
              type="button"
              role="radio"
              class="admin-swiss-segment"
              :class="{ 'is-active': exportFormat === opt.value }"
              :aria-checked="exportFormat === opt.value"
              @click="exportFormat = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <el-button
          class="admin-swiss-btn"
          :loading="downloading"
          @click="download"
        >
          {{ t('admin.mindmateExport.download') }}
        </el-button>
      </div>
    </section>

    <section
      v-if="showJobPanel"
      class="mindmate-export-card mindmate-export-job"
    >
      <div class="mindmate-export-job-header">
        <h3
          v-if="activeJob"
          class="mindmate-export-subtitle"
        >
          {{ t('admin.mindmateExport.jobProgress', {
            percent: activeJob.progress_percent,
            stage: activeJob.current_stage ?? activeJob.status,
          }) }}
        </h3>
        <h3
          v-else
          class="mindmate-export-subtitle"
        >
          {{ t('admin.mindmateExport.download') }}
        </h3>
        <span
          v-if="displayVerificationStatus()"
          class="mindmate-export-verify-badge"
          :class="verificationBadgeClass(displayVerificationStatus())"
        >
          {{ verificationBadgeLabel(displayVerificationStatus()) }}
        </span>
      </div>
      <p
        v-if="requiresJob && activeJobId == null"
        class="mindmate-export-requires-job"
      >
        {{ t('admin.mindmateExport.requiresJobNotice') }}
      </p>
      <el-progress
        v-if="activeJob"
        :percentage="activeJob.progress_percent"
        :stroke-width="8"
        :show-text="false"
        class="mindmate-export-job-bar"
      />
      <p
        v-if="exportDataSourceSummary"
        class="mindmate-export-meta-line"
      >
        {{ t('admin.mindmateExport.dataSource', { summary: exportDataSourceSummary }) }}
      </p>
      <p
        v-if="activeJob?.error_message"
        class="mindmate-export-truncated"
      >
        {{ activeJob.error_message }}
      </p>
      <div class="mindmate-export-job-actions">
        <el-button
          v-if="activeJob?.status === 'running' || activeJob?.status === 'pending'"
          class="admin-swiss-btn"
          :loading="jobActionPending"
          @click="pauseJob"
        >
          {{ t('admin.mindmateExport.jobPause') }}
        </el-button>
        <el-button
          v-if="activeJob?.status === 'paused'"
          class="admin-swiss-btn"
          :loading="jobActionPending"
          @click="resumeJob"
        >
          {{ t('admin.mindmateExport.jobResume') }}
        </el-button>
        <el-button
          v-if="activeJob && !jobIsTerminal"
          class="admin-swiss-btn"
          :loading="jobActionPending"
          @click="cancelJob"
        >
          {{ t('admin.mindmateExport.jobCancel') }}
        </el-button>
        <el-button
          v-if="jobCanDownload"
          class="admin-swiss-btn admin-swiss-btn--primary"
          :loading="downloading"
          @click="downloadJobArtifact"
        >
          {{ t('admin.mindmateExport.jobDownload') }}
        </el-button>
        <el-button
          v-if="requiresJob && activeJobId == null"
          type="primary"
          class="admin-swiss-btn admin-swiss-btn--primary"
          :loading="downloading"
          @click="startExportJob"
        >
          {{ t('admin.mindmateExport.download') }}
        </el-button>
      </div>
    </section>

    <section class="mindmate-export-body">
      <div class="mindmate-export-card mindmate-export-list">
        <div class="mindmate-export-list-header">
          <h3 class="mindmate-export-subtitle">
            {{ t('admin.mindmateExport.conversationsTitle') }}
            <span
              v-if="conversations.length"
              class="mindmate-export-count"
            >
              {{ t('admin.mindmateExport.conversationCount', { count: conversations.length }) }}
            </span>
          </h3>
          <span
            v-if="listVerificationStatus && hasLoadedConversations"
            class="mindmate-export-verify-badge"
            :class="verificationBadgeClass(listVerificationStatus)"
          >
            {{ verificationBadgeLabel(listVerificationStatus) }}
          </span>
        </div>
        <div
          v-if="hasLoadedConversations && !loadingConversations"
          class="mindmate-export-stats"
        >
          <span class="mindmate-export-stat">
            {{ listStats.usersScanned }}/{{ listStats.usersTotal }}
            {{ t('admin.mindmateExport.usersLabel') }}
          </span>
          <span class="mindmate-export-stat">
            {{ listStats.targetsCount }} targets
          </span>
          <span class="mindmate-export-stat">
            {{ listStats.conversationsTotal }}
            {{ t('admin.mindmateExport.conversationsTitle').toLowerCase() }}
          </span>
          <span
            v-if="listStats.partialFailures > 0"
            class="mindmate-export-stat mindmate-export-stat--warn"
          >
            {{ listStats.partialFailures }} partial failures
          </span>
        </div>
        <p
          v-if="requiresJob && hasLoadedConversations"
          class="mindmate-export-requires-job"
        >
          {{ t('admin.mindmateExport.requiresJobNotice') }}
        </p>
        <p
          v-for="(warning, wIdx) in exportWarnings"
          :key="`warn-${wIdx}`"
          class="mindmate-export-truncated"
        >
          {{ warning }}
        </p>
        <el-empty
          v-if="!hasLoadedConversations"
          :description="t('admin.mindmateExport.loadPrompt')"
        />
        <el-empty
          v-else-if="loadingConversations && conversations.length === 0"
          :description="t('admin.mindmateExport.loading')"
        />
        <el-empty
          v-else-if="!loadingConversations && conversations.length === 0"
          :description="t('admin.mindmateExport.noConversations')"
        />
        <ul
          v-else
          class="mindmate-export-conv-items"
        >
          <li
            v-for="conv in conversations"
            :key="conversationKey(conv)"
            class="mindmate-export-conv-item"
            :class="{
              'is-active':
                activeConversation != null && conversationKey(activeConversation) === conversationKey(conv),
            }"
            @click="openTranscript(conv)"
          >
            <div class="mindmate-export-conv-main">
              <span class="mindmate-export-conv-name">{{
                conv.name || conv.conversation_id
              }}</span>
              <span
                v-if="scopeMode === 'all'"
                class="mindmate-export-conv-org"
              >
                {{ orgLabel(conv.organization_id) }}
              </span>
              <span class="mindmate-export-conv-user">{{ conv.user_label }}</span>
            </div>
            <div class="mindmate-export-conv-meta">
              <span
                class="mindmate-export-channel-badge"
                :class="conv.channel === 'mindbot' ? 'is-mindbot' : 'is-web'"
              >
                {{ channelLabel(conv.channel) }}
              </span>
              <span
                v-if="chatScopeLabel(conv.dingtalk_chat_scope)"
                class="mindmate-export-chat-scope-badge"
                :class="chatScopeClass(conv.dingtalk_chat_scope)"
              >
                {{ chatScopeLabel(conv.dingtalk_chat_scope) }}
              </span>
              <span
                class="mindmate-export-server-badge"
                :class="conv.server === 2 ? 'is-secondary' : 'is-primary'"
              >
                {{ t('admin.mindmateExport.serverBadge', { server: conv.server }) }}
              </span>
              <span class="mindmate-export-conv-time">{{ formatTime(conv.updated_at) }}</span>
            </div>
          </li>
        </ul>
        <div
          v-if="listHasMore && conversations.length > 0"
          class="mindmate-export-load-more"
        >
          <el-button
            class="admin-swiss-btn"
            :loading="loadingMore"
            @click="loadMoreConversations"
          >
            {{ t('admin.mindmateExport.loadMore') }}
          </el-button>
        </div>
      </div>

      <div class="mindmate-export-card mindmate-export-transcript">
        <h3 class="mindmate-export-subtitle">{{ t('admin.mindmateExport.transcriptTitle') }}</h3>
        <div
          v-if="loadingBubbles"
          class="mindmate-export-loading"
        >
          {{ t('admin.mindmateExport.loading') }}
        </div>
        <el-empty
          v-else-if="!activeConversation"
          :description="t('admin.mindmateExport.viewTranscript')"
        />
        <el-empty
          v-else-if="bubbles.length === 0"
          :description="t('admin.mindmateExport.noMessages')"
        />
        <div
          v-else
          class="mindmate-export-bubbles"
        >
          <div
            v-for="(bubble, idx) in bubbles"
            :key="`${bubble.message_id}:${idx}`"
            class="mindmate-export-bubble"
            :class="bubble.role === 'user' ? 'is-user' : 'is-assistant'"
          >
            <div class="mindmate-export-bubble-role">{{ bubbleRoleLabel(bubble.role) }}</div>
            <div class="mindmate-export-bubble-text">{{ bubble.text }}</div>
            <div
              v-if="bubble.feedback"
              class="mindmate-export-bubble-feedback"
            >
              {{ t('admin.mindmateExport.feedbackLabel') }}: {{ bubble.feedback }}
            </div>
            <div class="mindmate-export-bubble-time">{{ formatTime(bubble.created_at) }}</div>
          </div>
        </div>
      </div>
    </section>
    </template>
    <AdminMindMateExportDumpsTab v-else-if="panelTab === 'dumps'" />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>

<style scoped>
.mindmate-export-page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mindmate-export-privacy {
  margin: 0;
  padding: 0.75rem 1rem;
  border: 1px solid var(--swiss-geek-amber-soft, #fffbeb);
  border-radius: 8px;
  background: var(--swiss-geek-amber-soft, #fffbeb);
  font-size: 0.8125rem;
  line-height: 1.5;
  color: var(--swiss-geek-amber-ui, #b45309);
}

.mindmate-export-job {
  padding: 0.875rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.mindmate-export-job-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.mindmate-export-job-header .mindmate-export-subtitle {
  margin: 0;
}

.mindmate-export-job-bar {
  max-width: 100%;
}

.mindmate-export-job-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.mindmate-export-requires-job {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--swiss-geek-amber-ui, #b45309);
}

.mindmate-export-list-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.625rem;
}

.mindmate-export-list-header .mindmate-export-subtitle {
  margin: 0;
}

.mindmate-export-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.625rem;
}

.mindmate-export-stat {
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--swiss-muted, #78716c);
  font-variant-numeric: tabular-nums;
}

.mindmate-export-stat--warn {
  color: var(--swiss-geek-amber-ui, #b45309);
}

.mindmate-export-verify-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.mindmate-export-verify-badge.is-pass {
  background: var(--swiss-geek-teal-soft, #f0fdfa);
  color: var(--swiss-geek-teal-ui, #0f766e);
}

.mindmate-export-verify-badge.is-gaps {
  background: var(--swiss-geek-amber-soft, #fffbeb);
  color: var(--swiss-geek-amber-ui, #b45309);
}

.mindmate-export-verify-badge.is-fail {
  background: #fef2f2;
  color: #b91c1c;
}

.mindmate-export-load-more {
  display: flex;
  justify-content: center;
  padding-top: 0.625rem;
}

.mindmate-export-card {
  border: 1px solid var(--swiss-border, #e7e5e4);
  border-radius: 12px;
  background: var(--swiss-surface, #ffffff);
}

.mindmate-export-filters {
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mindmate-export-filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem 1.25rem;
  align-items: end;
}

.mindmate-export-field {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  min-width: 0;
}

.mindmate-export-field--org,
.mindmate-export-field--users {
  grid-column: span 1;
}

.mindmate-export-field--dates {
  grid-column: 1 / -1;
  max-width: 100%;
  gap: 0.5rem;
}

.mindmate-export-dates-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.375rem;
}

.mindmate-export-dates-toolbar .mindmate-export-label {
  flex-shrink: 0;
  margin: 0;
}

.mindmate-export-presets {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.375rem;
}

.mindmate-export-preset {
  margin: 0;
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--swiss-border-strong, #d6d3d1);
  border-radius: 9999px;
  background: var(--swiss-inset, #fafaf9);
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  line-height: 1.35;
  color: var(--swiss-muted, #78716c);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.mindmate-export-preset.is-active {
  background: var(--swiss-ink, #1c1917);
  border-color: var(--swiss-ink, #1c1917);
  color: var(--swiss-surface, #ffffff);
  font-weight: 600;
}

.mindmate-export-preset:hover {
  border-color: var(--swiss-subtle, #a8a29e);
  color: var(--swiss-ink, #1c1917);
  background: var(--swiss-hover, #f5f5f4);
}

.mindmate-export-preset:focus-visible {
  outline: 2px solid var(--swiss-muted, #78716c);
  outline-offset: 2px;
}

.mindmate-export-dates-hint {
  margin: 0.375rem 0 0;
  font-size: 0.6875rem;
  line-height: 1.45;
  color: var(--swiss-muted, #78716c);
}

.mindmate-export-label {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--swiss-muted, #78716c);
}

.mindmate-export-label--inline {
  flex-shrink: 0;
}

.mindmate-export-select--org :deep(.el-select__wrapper),
.mindmate-export-select--users :deep(.el-select__wrapper) {
  min-height: 2rem;
  width: 100%;
  max-width: none;
}

.mindmate-export-select--org.admin-swiss-select,
.mindmate-export-select--users.admin-swiss-select {
  width: 100%;
  max-width: none;
}

.mindmate-export-date {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.mindmate-export-date.el-date-editor--datetimerange {
  --el-date-editor-width: 100%;
}

.mindmate-export-date :deep(.el-input__wrapper) {
  min-height: 2rem;
  width: 100%;
  max-width: 100%;
  display: flex;
  align-items: center;
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--swiss-ink, #1c1917);
  background-color: var(--swiss-inset, #fafaf9);
  border: 1px solid var(--swiss-border-strong, #d6d3d1);
  border-radius: 6px;
  box-shadow: none;
  box-sizing: border-box;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.mindmate-export-date :deep(.el-range-input) {
  flex: 1 1 0;
  min-width: 0;
  width: 0;
  color: var(--swiss-ink, #1c1917);
  font-size: 0.75rem;
}

.mindmate-export-date :deep(.el-range-separator) {
  flex-shrink: 0;
  padding: 0 0.2rem;
  color: var(--swiss-muted, #78716c);
  font-size: 0.75rem;
}

.mindmate-export-date :deep(.el-range__icon),
.mindmate-export-date :deep(.el-range__close-icon) {
  flex-shrink: 0;
}

.mindmate-export-date :deep(.el-input__wrapper:hover) {
  border-color: var(--swiss-subtle, #a8a29e);
}

.mindmate-export-date :deep(.el-input__wrapper.is-focus) {
  border-color: var(--swiss-muted, #78716c);
  box-shadow: 0 0 0 1px var(--swiss-border-strong, #d6d3d1);
}

.mindmate-export-date :deep(.el-input__inner),
.mindmate-export-date :deep(.el-range-input) {
  color: var(--swiss-ink, #1c1917);
}

.mindmate-export-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.mindmate-export-format {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.mindmate-export-format .mindmate-export-label--inline {
  line-height: 2rem;
}

.mindmate-export-body {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(320px, 1.3fr);
  gap: 1rem;
}

@media (max-width: 900px) {
  .mindmate-export-body {
    grid-template-columns: 1fr;
  }

  .mindmate-export-format {
    margin-left: 0;
    width: 100%;
  }
}

.mindmate-export-list,
.mindmate-export-transcript {
  padding: 0.875rem 1rem 1rem;
  min-height: 320px;
}

.mindmate-export-subtitle {
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  margin: 0 0 0.625rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--swiss-ink, #1c1917);
}

.mindmate-export-count {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--swiss-muted, #78716c);
}

.mindmate-export-truncated {
  margin: 0 0 0.625rem;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--swiss-geek-amber-ui, #b45309);
}

.mindmate-export-conv-items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  max-height: 520px;
  overflow-y: auto;
}

.mindmate-export-conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.mindmate-export-conv-item:hover {
  background: var(--swiss-hover, #f5f5f4);
}

.mindmate-export-conv-item.is-active {
  background: var(--swiss-inset, #fafaf9);
  border-color: var(--swiss-border-strong, #d6d3d1);
}

.mindmate-export-conv-main {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  min-width: 0;
}

.mindmate-export-conv-name {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--swiss-ink, #1c1917);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mindmate-export-conv-org {
  font-size: 0.6875rem;
  color: var(--swiss-muted, #78716c);
  font-weight: 500;
}

.mindmate-export-conv-user {
  font-size: 0.6875rem;
  color: var(--swiss-muted, #78716c);
}

.mindmate-export-conv-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
  flex-shrink: 0;
}

.mindmate-export-server-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.mindmate-export-server-badge.is-primary {
  background: var(--swiss-geek-teal-soft, #f0fdfa);
  color: var(--swiss-geek-teal-ui, #0f766e);
}

.mindmate-export-server-badge.is-secondary {
  background: var(--swiss-geek-amber-soft, #fffbeb);
  color: var(--swiss-geek-amber-ui, #b45309);
}

.mindmate-export-channel-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.mindmate-export-channel-badge.is-web {
  background: var(--swiss-geek-violet-soft, #f5f3ff);
  color: var(--swiss-geek-violet-ui, #7c3aed);
}

.mindmate-export-channel-badge.is-mindbot {
  background: var(--swiss-geek-cyan-soft, #ecfeff);
  color: var(--swiss-geek-cyan-ui, #0e7490);
}

.mindmate-export-chat-scope-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.mindmate-export-chat-scope-badge.is-group {
  background: #e6fcf5;
  color: #087f5b;
}

.mindmate-export-chat-scope-badge.is-cross-org {
  background: #fff0f6;
  color: #c2255c;
}

.mindmate-export-chat-scope-badge.is-oto {
  background: #f3f0ff;
  color: #5f3dc4;
}

.mindmate-export-conv-time {
  font-size: 0.6875rem;
  color: var(--swiss-muted, #78716c);
  font-variant-numeric: tabular-nums;
}

.mindmate-export-bubbles {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 520px;
  overflow-y: auto;
  padding: 0.25rem;
}

.mindmate-export-bubble {
  max-width: 78%;
  padding: 0.5rem 0.75rem;
  border-radius: 10px;
  font-size: 0.8125rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.mindmate-export-bubble.is-user {
  align-self: flex-end;
  background: var(--swiss-ink, #1c1917);
  color: var(--swiss-surface, #ffffff);
  border-bottom-right-radius: 2px;
}

.mindmate-export-bubble.is-user .mindmate-export-bubble-role,
.mindmate-export-bubble.is-user .mindmate-export-bubble-time {
  color: rgb(250 250 249 / 72%);
}

.mindmate-export-bubble.is-assistant {
  align-self: flex-start;
  background: var(--swiss-inset, #fafaf9);
  border: 1px solid var(--swiss-border, #e7e5e4);
  color: var(--swiss-body, #44403c);
  border-bottom-left-radius: 2px;
}

.mindmate-export-bubble-role {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--swiss-muted, #78716c);
  margin-bottom: 0.125rem;
}

.mindmate-export-bubble-feedback {
  margin-top: 0.25rem;
  font-size: 0.6875rem;
  color: var(--swiss-geek-violet-ui, #7c3aed);
}

.mindmate-export-bubble-time {
  margin-top: 0.25rem;
  font-size: 0.625rem;
  color: var(--swiss-subtle, #a8a29e);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.mindmate-export-loading {
  padding: 1.5rem;
  text-align: center;
  font-size: 0.8125rem;
  color: var(--swiss-muted, #78716c);
}
</style>
