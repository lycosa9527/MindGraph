<script setup lang="ts">
/**
 * MindBot admin — usage events (Log / Monitor) from /api/mindbot/admin/configs/:id/usage-events
 */
import { ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  organizationId: number | null
  canLoad: boolean
  staffFilter: boolean
}>()

const { t } = useLanguage()
const notify = useNotifications()

interface MindbotUsageEventRow {
  id: number
  dingtalk_staff_id: string
  sender_nick: string | null
  error_code: string
  duration_seconds: number | null
  prompt_chars: number
  reply_chars: number
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  msg_id: string | null
  dingtalk_conversation_id: string | null
  dify_conversation_id: string | null
  dingtalk_chat_scope: string | null
  conversation_user_turn: number | null
  created_at: string
}

const events = ref<MindbotUsageEventRow[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const cursorBeforeId = ref<number | null>(null)
const hasMore = ref(true)
const staffOptions = ref<{ label: string; value: string }[]>([])
const selectedStaffId = ref<string | null>(null)

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
    if (props.staffFilter && selectedStaffId.value) {
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
    if (props.staffFilter && !selectedStaffId.value) {
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
  const t = row.total_tokens
  if (t != null) {
    return String(t)
  }
  const p = row.prompt_tokens
  const c = row.completion_tokens
  if (p != null || c != null) {
    return `${p ?? '—'} / ${c ?? '—'}`
  }
  return '—'
}

watch(
  () => [props.organizationId, props.canLoad, props.staffFilter],
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
  if (!props.staffFilter) {
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

      <el-table
        v-if="events.length > 0"
        :data="events"
        stripe
        size="small"
        class="w-full"
        max-height="320"
      >
        <el-table-column
          :label="t('admin.mindbot.colTime')"
          min-width="150"
        >
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindbot.colStaff')"
          min-width="140"
        >
          <template #default="{ row }">
            <span class="text-xs">{{ row.sender_nick || row.dingtalk_staff_id }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="error_code"
          :label="t('admin.mindbot.colError')"
          width="100"
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
          :label="t('admin.mindbot.colTokens')"
          width="72"
        >
          <template #default="{ row }">
            {{ formatTokens(row) }}
          </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindbot.colChars')"
          width="100"
        >
          <template #default="{ row }"> {{ row.prompt_chars }} / {{ row.reply_chars }} </template>
        </el-table-column>
        <el-table-column
          :label="t('admin.mindbot.colTurn')"
          width="64"
        >
          <template #default="{ row }">
            {{ row.conversation_user_turn ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column
          prop="msg_id"
          :label="t('admin.mindbot.colMsgId')"
          min-width="100"
          show-overflow-tooltip
        />
        <el-table-column
          prop="dify_conversation_id"
          :label="t('admin.mindbot.colDifyConv')"
          min-width="100"
          show-overflow-tooltip
        />
        <el-table-column
          prop="dingtalk_conversation_id"
          :label="t('admin.mindbot.colDtConv')"
          min-width="100"
          show-overflow-tooltip
        />
        <el-table-column
          prop="dingtalk_chat_scope"
          :label="t('admin.mindbot.colScope')"
          width="80"
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
  </div>
</template>
