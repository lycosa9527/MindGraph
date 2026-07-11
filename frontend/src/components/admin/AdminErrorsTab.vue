<script setup lang="ts">
/**
 * Admin Error Collection — Swiss metrics + monospace event log (geek ops style).
 */
import { computed, ref, watch } from 'vue'
import { Bell, Connection, WarningFilled } from '@element-plus/icons-vue'

import AdminErrorEventDetailDialog from '@/components/admin/AdminErrorEventDetailDialog.vue'
import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import AdminSwissPagination from '@/components/admin/AdminSwissPagination.vue'
import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  fetchAdminErrorEventDetail,
  muteAdminErrorGroup,
  type AdminErrorEventItem,
  type AdminErrorGroupItem,
  type AdminErrorSummaryResponse,
} from '@/composables/queries/adminApi'
import {
  useAdminErrorEvents,
  useAdminErrorGroups,
  useAdminErrorSummary,
} from '@/composables/queries/useAdminQueries'

const { t } = useLanguage()
const notify = useNotifications()

type ViewMode = 'events' | 'groups'
type HoursWindow = 24 | 168 | 720

const viewMode = ref<ViewMode>('events')
const hours = ref<HoursWindow>(24)
const severity = ref<string>('')
const source = ref<string>('')
const page = ref(1)
const pageSize = 50

const detailVisible = ref(false)
const detailEvent = ref<(AdminErrorEventItem & { stacktrace?: string | null }) | null>(null)
const mutingGroupId = ref<number | null>(null)

const listQuery = computed(() => ({
  page: page.value,
  page_size: pageSize,
  hours: hours.value,
  severity: severity.value || undefined,
  source: source.value || undefined,
}))

const summaryQuery = useAdminErrorSummary()
const eventsQuery = useAdminErrorEvents(listQuery, {
  enabled: computed(() => viewMode.value === 'events'),
})
const groupsQuery = useAdminErrorGroups(listQuery, {
  enabled: computed(() => viewMode.value === 'groups'),
})

const summary = computed(() => summaryQuery.data.value as AdminErrorSummaryResponse | undefined)
const events = computed(() => eventsQuery.data.value?.events ?? [])
const groups = computed(() => groupsQuery.data.value?.groups ?? [])
const total = computed(() =>
  viewMode.value === 'events'
    ? (eventsQuery.data.value?.total ?? 0)
    : (groupsQuery.data.value?.total ?? 0)
)
const totalPages = computed(() =>
  viewMode.value === 'events'
    ? (eventsQuery.data.value?.total_pages ?? 1)
    : (groupsQuery.data.value?.total_pages ?? 1)
)

const loading = computed(
  () =>
    summaryQuery.isFetching.value ||
    (viewMode.value === 'events' ? eventsQuery.isFetching.value : groupsQuery.isFetching.value)
)
const fetchError = computed(
  () =>
    summaryQuery.error.value?.message ??
    eventsQuery.error.value?.message ??
    groupsQuery.error.value?.message ??
    null
)

const hoursOptions = computed(() => [
  { label: t('admin.errors.last24h'), value: 24 as HoursWindow },
  { label: t('admin.errors.last7d'), value: 168 as HoursWindow },
  { label: t('admin.errors.last30d'), value: 720 as HoursWindow },
])

const viewOptions = computed(() => [
  { label: t('admin.errors.viewEvents'), value: 'events' as ViewMode },
  { label: t('admin.errors.viewGroups'), value: 'groups' as ViewMode },
])

const severityOptions = ['', 'critical', 'error', 'warning']
const sourceOptions = ['', 'application', 'llm', 'frontend', 'background', 'mindbot', 'rag', 'collab', 'auth']

const severityBreakdown = computed(() => {
  const raw = summary.value?.by_severity_24h ?? {}
  return Object.entries(raw).sort((a, b) => b[1] - a[1])
})

const sourceBreakdown = computed(() => {
  const raw = summary.value?.by_source_24h ?? {}
  return Object.entries(raw).sort((a, b) => b[1] - a[1])
})

const pageInfo = computed(() =>
  t('admin.errors.pageInfo', {
    page: String(page.value),
    totalPages: String(totalPages.value),
    total: String(total.value),
  })
)

function formatTime(value: string): string {
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function shortFingerprint(fp: string): string {
  if (fp.length <= 16) {
    return fp
  }
  return `${fp.slice(0, 8)}…${fp.slice(-6)}`
}

function severityLineClass(sev: string): string {
  const s = sev.toLowerCase()
  if (s === 'critical' || s === 'error') {
    return 'admin-error-log-line--danger'
  }
  if (s === 'warning') {
    return 'admin-error-log-line--warn'
  }
  return 'admin-error-log-line--muted'
}

function formatEventLogLine(row: AdminErrorEventItem): string {
  const time = formatTime(row.created_at)
  const sev = row.severity.toUpperCase().padEnd(8, ' ')
  const src = row.source.padEnd(11, ' ')
  const comp = row.component.slice(0, 24).padEnd(24, ' ')
  const typ = row.exception_type.slice(0, 28)
  const path = row.http_path ? ` path=${row.http_path}` : ''
  const req = row.request_id ? ` req=${shortFingerprint(row.request_id)}` : ''
  const fp = ` fp=${shortFingerprint(row.fingerprint)}`
  const msg =
    row.message.length > 120 ? `${row.message.slice(0, 120)}…` : row.message
  return `[${time}] ${sev} ${src} ${comp} ${typ} id=${row.id}${path}${req}${fp} :: ${msg}`
}

function hasTextSelection(): boolean {
  const selection = window.getSelection()
  return Boolean(selection && selection.toString().trim().length > 0)
}

async function openEventDetail(eventId: number): Promise<void> {
  if (hasTextSelection()) {
    return
  }
  detailEvent.value = null
  try {
    detailEvent.value = await fetchAdminErrorEventDetail(eventId)
    detailVisible.value = true
  } catch {
    notify.error(t('admin.errors.detailLoadError'))
  }
}

function onEventLogKeydown(event: KeyboardEvent, eventId: number): void {
  if (event.key !== 'Enter' && event.key !== ' ') {
    return
  }
  event.preventDefault()
  void openEventDetail(eventId)
}

async function toggleGroupMute(group: AdminErrorGroupItem): Promise<void> {
  mutingGroupId.value = group.id
  try {
    await muteAdminErrorGroup(group.id, !group.muted)
    notify.success(
      group.muted ? t('admin.errors.unmuteSuccess') : t('admin.errors.muteSuccess')
    )
    void groupsQuery.refetch()
    void summaryQuery.refetch()
  } catch {
    notify.error(t('admin.errors.muteError'))
  } finally {
    mutingGroupId.value = null
  }
}

watch([hours, severity, source, viewMode], () => {
  page.value = 1
})

function refreshAll(): void {
  void summaryQuery.refetch()
  if (viewMode.value === 'events') {
    void eventsQuery.refetch()
  } else {
    void groupsQuery.refetch()
  }
}

function onPreviousPage(): void {
  if (page.value > 1) {
    page.value -= 1
  }
}

function onNextPage(): void {
  if (page.value < totalPages.value) {
    page.value += 1
  }
}
</script>

<template>
  <div
    v-loading="loading && !summary"
    class="max-w-[1400px] mx-auto space-y-6 pb-8"
  >
    <p
      v-if="fetchError"
      class="text-sm text-[var(--swiss-stat-danger-accent,#e30613)]"
    >
      {{ fetchError }}
    </p>

    <section aria-labelledby="errors-kpi-overview">
      <h3
        id="errors-kpi-overview"
        class="swiss-stat-card-group__title"
      >
        {{ t('admin.errors.groupOverview') }}
      </h3>
      <div class="swiss-stat-card-grid swiss-stat-card-grid--wide">
        <AdminSwissKpiCard
          :title="t('admin.errors.events24h')"
          :value="summary?.total_events_24h ?? '—'"
          :icon="WarningFilled"
          theme="danger"
        />
        <AdminSwissKpiCard
          :title="t('admin.errors.events7d')"
          :value="summary?.total_events_7d ?? '—'"
          theme="warn"
        />
        <AdminSwissKpiCard
          :title="t('admin.errors.alertWebhook')"
          :value="
            summary?.alert_config?.webhook_configured
              ? t('admin.errors.configured')
              : t('admin.errors.notConfigured')
          "
          :icon="Connection"
          theme="integration"
        />
        <AdminSwissKpiCard
          :title="t('admin.errors.alertDingtalk')"
          :value="
            summary?.alert_config?.dingtalk_configured
              ? t('admin.errors.configured')
              : t('admin.errors.notConfigured')
          "
          :icon="Bell"
          theme="platform"
        />
      </div>
    </section>

    <section
      v-if="severityBreakdown.length > 0 || sourceBreakdown.length > 0"
      aria-labelledby="errors-breakdown"
    >
      <h3
        id="errors-breakdown"
        class="swiss-stat-card-group__title"
      >
        {{ t('admin.errors.groupBreakdown') }}
      </h3>
      <div class="grid gap-4 md:grid-cols-2">
        <div
          v-if="severityBreakdown.length > 0"
          class="rounded-lg border border-stone-200 dark:border-stone-600 p-3"
        >
          <p class="text-xs font-medium text-[var(--swiss-muted)] mb-2 uppercase tracking-wide">
            {{ t('admin.errors.bySeverity24h') }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="[key, count] in severityBreakdown"
              :key="key"
              class="swiss-stat-card__stat-pill"
            >
              <span class="swiss-stat-card__stat-pill-k font-mono">{{ key }}</span>
              <span class="swiss-stat-card__stat-pill-v">{{ count }}</span>
            </span>
          </div>
        </div>
        <div
          v-if="sourceBreakdown.length > 0"
          class="rounded-lg border border-stone-200 dark:border-stone-600 p-3"
        >
          <p class="text-xs font-medium text-[var(--swiss-muted)] mb-2 uppercase tracking-wide">
            {{ t('admin.errors.bySource24h') }}
          </p>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="[key, count] in sourceBreakdown"
              :key="key"
              class="swiss-stat-card__stat-pill"
            >
              <span class="swiss-stat-card__stat-pill-k font-mono">{{ key }}</span>
              <span class="swiss-stat-card__stat-pill-v">{{ count }}</span>
            </span>
          </div>
        </div>
      </div>
    </section>

    <section aria-labelledby="errors-feed">
      <h3
        id="errors-feed"
        class="swiss-stat-card-group__title"
      >
        {{ t('admin.errors.groupFeed') }}
      </h3>

      <p class="text-xs text-[var(--swiss-muted)] mb-3">
        {{ t('admin.errors.feedHint') }}
      </p>

      <div class="admin-swiss-toolbar admin-swiss-toolbar--header mb-3 flex-wrap">
        <AdminSwissSegmented
          v-model="viewMode"
          :options="viewOptions"
          equal
          fit
          :aria-label="t('admin.errors.viewMode')"
        />
        <AdminSwissSegmented
          v-model="hours"
          :options="hoursOptions"
          equal
          fit
          :aria-label="t('admin.errors.timeWindow')"
        />
        <el-select
          v-model="severity"
          class="admin-swiss-select admin-swiss-select--filter"
          clearable
          :placeholder="t('admin.errors.severity')"
        >
          <el-option
            v-for="opt in severityOptions"
            :key="opt || 'all-sev'"
            :label="opt || t('admin.errors.all')"
            :value="opt"
          />
        </el-select>
        <el-select
          v-model="source"
          class="admin-swiss-select admin-swiss-select--filter"
          clearable
          :placeholder="t('admin.errors.source')"
        >
          <el-option
            v-for="opt in sourceOptions"
            :key="opt || 'all-src'"
            :label="opt || t('admin.errors.all')"
            :value="opt"
          />
        </el-select>
        <el-button
          class="admin-swiss-btn admin-swiss-btn--ghost"
          :loading="loading"
          @click="refreshAll"
        >
          {{ t('common.refresh') }}
        </el-button>
      </div>

      <!-- Events: monospace log feed -->
      <div
        v-if="viewMode === 'events' && events.length > 0"
        v-loading="loading"
        class="rounded-lg border border-stone-200 dark:border-stone-600 overflow-hidden"
      >
        <div
          class="divide-y divide-stone-100 dark:divide-stone-700 max-h-[min(420px,55vh)] overflow-y-auto"
        >
          <div
            v-for="row in events"
            :key="row.id"
            role="button"
            tabindex="0"
            class="admin-error-log-line w-full text-left px-3 py-1.5 font-mono text-[11px] leading-snug hover:bg-stone-50 dark:hover:bg-stone-800/80 transition-colors cursor-pointer select-text"
            :class="severityLineClass(row.severity)"
            @click="openEventDetail(row.id)"
            @keydown="onEventLogKeydown($event, row.id)"
          >
            {{ formatEventLogLine(row) }}
          </div>
        </div>
      </div>

      <!-- Groups: compact table -->
      <div
        v-else-if="viewMode === 'groups' && groups.length > 0"
        v-loading="loading"
        class="rounded-lg border border-stone-200 dark:border-stone-600 overflow-hidden"
      >
        <el-table
          :data="groups"
          stripe
          size="small"
          class="w-full admin-error-groups-table"
          max-height="420"
        >
          <el-table-column
            :label="t('admin.errors.colCount')"
            width="72"
            prop="occurrence_count"
          />
          <el-table-column
            :label="t('admin.errors.severity')"
            width="88"
          >
            <template #default="{ row }">
              <span class="font-mono text-xs uppercase">{{ row.severity }}</span>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.errors.source')"
            width="100"
          >
            <template #default="{ row }">
              <span class="font-mono text-xs">{{ row.source }}</span>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.errors.component')"
            min-width="120"
            prop="component"
          />
          <el-table-column
            :label="t('admin.errors.type')"
            min-width="140"
            prop="exception_type"
          />
          <el-table-column
            :label="t('admin.errors.fingerprint')"
            width="120"
          >
            <template #default="{ row }">
              <span
                class="font-mono text-xs"
                :title="row.fingerprint"
              >{{ shortFingerprint(row.fingerprint) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.errors.colLastSeen')"
            min-width="150"
          >
            <template #default="{ row }">
              <span class="text-xs">{{ formatTime(row.last_seen_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.errors.message')"
            min-width="200"
            show-overflow-tooltip
            prop="sample_message"
          />
          <el-table-column
            :label="t('admin.errors.colMute')"
            width="88"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                size="small"
                class="admin-swiss-pill-btn"
                :loading="mutingGroupId === row.id"
                @click.stop="toggleGroupMute(row)"
              >
                {{ row.muted ? t('admin.errors.unmute') : t('admin.errors.mute') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <p
        v-else-if="!loading"
        class="text-sm text-[var(--swiss-muted)] py-8 text-center font-mono"
      >
        {{ t('admin.errors.emptyFeed') }}
      </p>

      <AdminSwissPagination
        v-if="total > 0"
        class="mt-3"
        :page="page"
        :total-pages="totalPages"
        :page-info="pageInfo"
        @previous="onPreviousPage"
        @next="onNextPage"
      />
    </section>

    <AdminErrorEventDetailDialog
      v-model="detailVisible"
      :event="detailEvent"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>

<style scoped>
.admin-error-log-line--danger {
  color: #9f1239;
}

html.dark .admin-error-log-line--danger {
  color: #fecdd3;
}

.admin-error-log-line--warn {
  color: #92400e;
}

html.dark .admin-error-log-line--warn {
  color: #fde68a;
}

.admin-error-log-line--muted {
  color: #57534e;
}

html.dark .admin-error-log-line--muted {
  color: #a8a29e;
}

.admin-error-groups-table :deep(.el-table__cell) {
  font-size: 12px;
}
</style>
