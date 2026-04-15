<script setup lang="ts">
/**
 * MindBot admin — usage: Log tab (grouped raw-style lines) and Monitor (by conversation + detail).
 */
import { computed, ref, watch } from 'vue'

import MindbotUsageEventDetailDialog from '@/components/admin/MindbotUsageEventDetailDialog.vue'
import {
  isMindbotUsageSuccess,
  mindbotThreadKey,
  type MindbotUsageEventRow,
} from '@/components/admin/mindbotUsageTypes'
import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  organizationId: number | null
  canLoad: boolean
  /** log: raw chronological lines; monitor: group by conversation thread */
  mode: 'log' | 'monitor'
}>()

const { t } = useLanguage()
const notify = useNotifications()

const staffFilter = computed(() => props.mode === 'monitor')

interface ThreadGroup {
  key: string
  dingtalk_staff_id: string
  sender_nick: string | null
  dingtalk_conversation_id: string | null
  dify_conversation_id: string | null
  lastEvent: MindbotUsageEventRow
  turnsInBatch: number
}

const events = ref<MindbotUsageEventRow[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const cursorBeforeId = ref<number | null>(null)
const hasMore = ref(true)
const staffOptions = ref<{ label: string; value: string }[]>([])
const selectedStaffId = ref<string | null>(null)

const detailVisible = ref(false)
const detailEvent = ref<MindbotUsageEventRow | null>(null)

const threadDrawerVisible = ref(false)
const threadLoading = ref(false)
const threadLoadingMore = ref(false)
const threadEvents = ref<MindbotUsageEventRow[]>([])
const threadCursorBeforeId = ref<number | null>(null)
const threadHasMore = ref(true)
const activeThread = ref<{
  dingtalk_staff_id: string
  dingtalk_conversation_id: string | null
  dify_conversation_id: string | null
} | null>(null)

const threadGroups = computed<ThreadGroup[]>(() => {
  if (props.mode !== 'monitor') {
    return []
  }
  const map = new Map<string, MindbotUsageEventRow[]>()
  for (const row of events.value) {
    const k = mindbotThreadKey(row)
    const list = map.get(k)
    if (list) {
      list.push(row)
    } else {
      map.set(k, [row])
    }
  }
  const out: ThreadGroup[] = []
  for (const [key, list] of map) {
    const lastEvent = list[0]
    if (!lastEvent) {
      continue
    }
    out.push({
      key,
      dingtalk_staff_id: lastEvent.dingtalk_staff_id,
      sender_nick: lastEvent.sender_nick,
      dingtalk_conversation_id: lastEvent.dingtalk_conversation_id,
      dify_conversation_id: lastEvent.dify_conversation_id,
      lastEvent,
      turnsInBatch: list.length,
    })
  }
  return out
})

const logGroups = computed(() => {
  if (props.mode !== 'log') {
    return []
  }
  const dayMap = new Map<string, MindbotUsageEventRow[]>()
  for (const row of events.value) {
    const day = row.created_at.slice(0, 10)
    const list = dayMap.get(day)
    if (list) {
      list.push(row)
    } else {
      dayMap.set(day, [row])
    }
  }
  const days = [...dayMap.keys()].sort((a, b) => (a < b ? 1 : a > b ? -1 : 0))
  return days.map((day) => ({
    day,
    events: dayMap.get(day) ?? [],
  }))
})

function mergeStaffFromBatch(batch: MindbotUsageEventRow[]): void {
  const seen = new Set(staffOptions.value.map((o) => o.value))
  for (const row of batch) {
    const sid = row.dingtalk_staff_id
    if (!sid || seen.has(sid)) {
      continue
    }
    seen.add(sid)
    const nick = row.sender_nick?.trim()
    staffOptions.value.push({
      value: sid,
      label: nick ? `${nick} (${sid})` : sid,
    })
  }
}

async function loadPage(append: boolean): Promise<void> {
  if (!props.canLoad || props.organizationId == null) {
    return
  }
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }
  try {
    const params = new URLSearchParams({ limit: '50' })
    if (append && cursorBeforeId.value != null) {
      params.set('before_id', String(cursorBeforeId.value))
    }
    if (staffFilter.value && selectedStaffId.value) {
      params.set('dingtalk_staff_id', selectedStaffId.value)
    }
    const res = await apiRequest(
      `/api/mindbot/admin/configs/${props.organizationId}/usage-events?${params.toString()}`
    )
    if (!res.ok) {
      notify.error(t('admin.mindbot.usageLoadError'))
      return
    }
    const batch = (await res.json()) as MindbotUsageEventRow[]
    if (append) {
      events.value = [...events.value, ...batch]
    } else {
      events.value = batch
    }
    if (staffFilter.value && !selectedStaffId.value) {
      mergeStaffFromBatch(batch)
    }
    if (batch.length === 0) {
      hasMore.value = false
      cursorBeforeId.value = null
    } else {
      cursorBeforeId.value = batch[batch.length - 1].id
      hasMore.value = batch.length >= 50
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function formatDur(s: number | null): string {
  if (s == null || Number.isNaN(s)) {
    return '—'
  }
  return s.toFixed(2)
}

function formatTokens(row: MindbotUsageEventRow): string {
  const tok = row.total_tokens
  if (tok != null) {
    return String(tok)
  }
  const p = row.prompt_tokens
  const c = row.completion_tokens
  if (p != null || c != null) {
    return `${p ?? '—'} / ${c ?? '—'}`
  }
  return '—'
}

function convShort(row: MindbotUsageEventRow): string {
  const dt = row.dingtalk_conversation_id?.trim()
  if (dt) {
    return dt.length > 28 ? `${dt.slice(0, 14)}…${dt.slice(-8)}` : dt
  }
  const df = row.dify_conversation_id?.trim()
  if (df) {
    return df.length > 28 ? `${df.slice(0, 14)}…${df.slice(-8)}` : df
  }
  return t('admin.mindbot.convNoThreadId')
}

function formatLogLine(row: MindbotUsageEventRow): string {
  const time = formatTime(row.created_at)
  const ok = isMindbotUsageSuccess(row.error_code) ? 'ok' : 'err'
  const scope = row.dingtalk_chat_scope ?? '—'
  const typ = row.inbound_msg_type ?? '—'
  const turn = row.conversation_user_turn ?? '—'
  const msg = row.msg_id ?? '—'
  const dt = row.dingtalk_conversation_id ?? '—'
  const df = row.dify_conversation_id ?? '—'
  return `[${time}] ${row.error_code} ${ok} dur=${formatDur(row.duration_seconds)}s stream=${row.streaming} turn=${turn} scope=${scope} type=${typ} staff=${row.dingtalk_staff_id} msg=${msg} dt=${dt} dify=${df} in=${row.prompt_chars}ch out=${row.reply_chars}ch tok=${formatTokens(row)}`
}

function openEventDetail(row: MindbotUsageEventRow): void {
  detailEvent.value = row
  detailVisible.value = true
}

async function openGroupRow(g: ThreadGroup): Promise<void> {
  if (g.key.startsWith('singleton:')) {
    openEventDetail(g.lastEvent)
    return
  }
  activeThread.value = {
    dingtalk_staff_id: g.dingtalk_staff_id,
    dingtalk_conversation_id: g.dingtalk_conversation_id,
    dify_conversation_id: g.dify_conversation_id,
  }
  threadDrawerVisible.value = true
  threadEvents.value = []
  threadCursorBeforeId.value = null
  threadHasMore.value = true
  await loadThreadPage(false)
}

async function loadThreadPage(append: boolean): Promise<void> {
  const orgId = props.organizationId
  const th = activeThread.value
  if (orgId == null || th == null) {
    return
  }
  if (append) {
    threadLoadingMore.value = true
  } else {
    threadLoading.value = true
  }
  try {
    const params = new URLSearchParams({
      limit: '50',
      dingtalk_staff_id: th.dingtalk_staff_id,
    })
    const dt = th.dingtalk_conversation_id?.trim()
    const df = th.dify_conversation_id?.trim()
    if (dt) {
      params.set('dingtalk_conversation_id', dt)
    } else if (df) {
      params.set('dify_conversation_id', df)
    } else {
      threadLoading.value = false
      threadLoadingMore.value = false
      return
    }
    if (append && threadCursorBeforeId.value != null) {
      params.set('before_id', String(threadCursorBeforeId.value))
    }
    const res = await apiRequest(
      `/api/mindbot/admin/configs/${orgId}/usage-thread-events?${params.toString()}`
    )
    if (!res.ok) {
      notify.error(t('admin.mindbot.usageLoadError'))
      return
    }
    const batch = (await res.json()) as MindbotUsageEventRow[]
    if (append) {
      threadEvents.value = [...threadEvents.value, ...batch]
    } else {
      threadEvents.value = batch
    }
    if (batch.length === 0) {
      threadHasMore.value = false
      threadCursorBeforeId.value = null
    } else {
      threadCursorBeforeId.value = batch[batch.length - 1].id
      threadHasMore.value = batch.length >= 50
    }
  } finally {
    threadLoading.value = false
    threadLoadingMore.value = false
  }
}

watch(
  () => [props.organizationId, props.canLoad, props.mode],
  () => {
    events.value = []
    cursorBeforeId.value = null
    hasMore.value = true
    staffOptions.value = []
    selectedStaffId.value = null
    void loadPage(false)
  },
  { immediate: true }
)

watch(selectedStaffId, () => {
  if (!staffFilter.value) {
    return
  }
  events.value = []
  cursorBeforeId.value = null
  hasMore.value = true
  void loadPage(false)
})

async function onLoadMore(): Promise<void> {
  await loadPage(true)
}

async function onThreadLoadMore(): Promise<void> {
  await loadThreadPage(true)
}

function onThreadDrawerClosed(): void {
  activeThread.value = null
  threadEvents.value = []
  threadCursorBeforeId.value = null
  threadHasMore.value = true
}

function onMonitorRowClick(row: ThreadGroup): void {
  void openGroupRow(row)
}
</script>

<template>
  <div class="mindbot-usage-panel">
    <p
      v-if="!canLoad"
      class="text-sm text-gray-600 dark:text-gray-400"
    >
      {{ t('admin.mindbot.usageNeedSave') }}
    </p>
    <div
      v-else
      v-loading="loading"
      class="space-y-3"
    >
      <p
        v-if="mode === 'log'"
        class="text-xs text-gray-500 dark:text-gray-400"
      >
        {{ t('admin.mindbot.logTabHint') }}
      </p>
      <p
        v-else
        class="text-xs text-gray-500 dark:text-gray-400"
      >
        {{ t('admin.mindbot.monitorTabHint') }}
      </p>

      <div
        v-if="staffFilter"
        class="flex flex-col gap-2 sm:flex-row sm:items-center"
      >
        <span class="text-xs text-gray-500 dark:text-gray-400 shrink-0">{{
          t('admin.mindbot.monitorFilterStaff')
        }}</span>
        <el-select
          v-model="selectedStaffId"
          class="w-full sm:max-w-md"
          clearable
          filterable
          :placeholder="t('admin.mindbot.monitorStaffAll')"
        >
          <el-option
            v-for="o in staffOptions"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
      </div>

      <!-- Log: grouped raw lines -->
      <div
        v-if="mode === 'log' && logGroups.length > 0"
        class="space-y-3 mindbot-log-groups"
      >
        <div
          v-for="g in logGroups"
          :key="g.day"
          class="rounded-lg border border-stone-200 dark:border-stone-600 overflow-hidden"
        >
          <div
            class="px-3 py-2 text-xs font-medium bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-200 font-mono"
          >
            {{ t('admin.mindbot.logDayGroup', { day: g.day }) }}
          </div>
          <div class="divide-y divide-stone-100 dark:divide-stone-700 max-h-[min(360px,50vh)] overflow-y-auto">
            <button
              v-for="row in g.events"
              :key="row.id"
              type="button"
              class="mindbot-log-line w-full text-left px-3 py-1.5 font-mono text-[11px] leading-snug hover:bg-stone-50 dark:hover:bg-stone-800/80 transition-colors"
              :class="
                isMindbotUsageSuccess(row.error_code)
                  ? 'text-emerald-800 dark:text-emerald-200'
                  : 'text-rose-800 dark:text-rose-200'
              "
              @click="openEventDetail(row)"
            >
              {{ formatLogLine(row) }}
            </button>
          </div>
        </div>
      </div>

      <!-- Monitor: conversation groups -->
      <el-table
        v-else-if="mode === 'monitor' && threadGroups.length > 0"
        :data="threadGroups"
        stripe
        size="small"
        class="w-full mindbot-monitor-table"
        max-height="320"
        row-class-name="mindbot-monitor-row"
        @row-click="onMonitorRowClick"
      >
        <el-table-column
          :label="t('admin.mindbot.colTime')"
          min-width="150"
        >
          <template #default="{ row }">
            {{ formatTime(row.lastEvent.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindbot.colStaff')"
          min-width="120"
        >
          <template #default="{ row }">
            <span class="text-xs">{{ row.sender_nick || row.dingtalk_staff_id }}</span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindbot.colConvThread')"
          min-width="140"
        >
          <template #default="{ row }">
            <span class="text-xs font-mono">{{ convShort(row.lastEvent) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindbot.colTurnsLoaded')"
          width="88"
        >
          <template #default="{ row }">
            {{ row.turnsInBatch }}
          </template>
        </el-table-column>
        <el-table-column
          prop="lastEvent.error_code"
          :label="t('admin.mindbot.colError')"
          width="120"
        />
      </el-table>

      <p
        v-else-if="!loading"
        class="text-sm text-gray-500 dark:text-gray-400 py-4 text-center"
      >
        {{ t('admin.mindbot.usageEmpty') }}
      </p>

      <div
        v-if="events.length > 0 && hasMore"
        class="flex justify-center pt-1"
      >
        <el-button
          size="small"
          :loading="loadingMore"
          @click="onLoadMore"
        >
          {{ t('admin.mindbot.loadMore') }}
        </el-button>
      </div>
    </div>

    <MindbotUsageEventDetailDialog
      v-model="detailVisible"
      :event="detailEvent"
    />

    <el-drawer
      v-model="threadDrawerVisible"
      :title="t('admin.mindbot.conversationDrawerTitle')"
      size="min(520px, 92vw)"
      destroy-on-close
      @closed="onThreadDrawerClosed"
    >
      <div
        v-loading="threadLoading"
        class="space-y-2"
      >
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {{ t('admin.mindbot.conversationDrawerHint') }}
        </p>
        <el-table
          v-if="threadEvents.length > 0"
          :data="threadEvents"
          stripe
          size="small"
          max-height="360"
          class="w-full mindbot-thread-table"
          row-class-name="mindbot-thread-row"
          @row-click="(row: MindbotUsageEventRow) => openEventDetail(row)"
        >
          <el-table-column
            :label="t('admin.mindbot.colTime')"
            min-width="140"
          >
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="error_code"
            :label="t('admin.mindbot.colError')"
            width="120"
          />
          <el-table-column
            :label="t('admin.mindbot.colDuration')"
            width="88"
          >
            <template #default="{ row }">
              {{ formatDur(row.duration_seconds) }}
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.mindbot.colTurn')"
            width="64"
          >
            <template #default="{ row }">
              {{ row.conversation_user_turn ?? '—' }}
            </template>
          </el-table-column>
        </el-table>
        <p
          v-else-if="!threadLoading"
          class="text-sm text-gray-500"
        >
          {{ t('admin.mindbot.threadEmpty') }}
        </p>
        <div
          v-if="threadEvents.length > 0 && threadHasMore"
          class="flex justify-center"
        >
          <el-button
            size="small"
            :loading="threadLoadingMore"
            @click="onThreadLoadMore"
          >
            {{ t('admin.mindbot.threadLoadMore') }}
          </el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.mindbot-monitor-table :deep(.mindbot-monitor-row) {
  cursor: pointer;
}
.mindbot-monitor-table :deep(.mindbot-monitor-row:hover > td) {
  background-color: rgba(245, 245, 244, 0.9);
}
.dark .mindbot-monitor-table :deep(.mindbot-monitor-row:hover > td) {
  background-color: rgba(41, 49, 65, 0.55);
}
.mindbot-thread-table :deep(.mindbot-thread-row) {
  cursor: pointer;
}
.mindbot-thread-table :deep(.mindbot-thread-row:hover > td) {
  background-color: rgba(245, 245, 244, 0.9);
}
.dark .mindbot-thread-table :deep(.mindbot-thread-row:hover > td) {
  background-color: rgba(41, 49, 65, 0.55);
}
</style>
