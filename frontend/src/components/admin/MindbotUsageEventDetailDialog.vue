<script setup lang="ts">
import { computed } from 'vue'

import type { MindbotUsageEventRow } from '@/components/admin/mindbotUsageTypes'
import { useLanguage } from '@/composables'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  event: MindbotUsageEventRow | null
}>()

const { t } = useLanguage()

const title = computed(() => t('admin.mindbot.usageEventDetailTitle'))

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
  return s.toFixed(3)
}

function formatTokens(row: MindbotUsageEventRow): string {
  const tot = row.total_tokens
  if (tot != null) {
    return String(tot)
  }
  const p = row.prompt_tokens
  const c = row.completion_tokens
  if (p != null || c != null) {
    return `${p ?? '—'} / ${c ?? '—'}`
  }
  return '—'
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="min(560px, 92vw)"
    class="mindbot-usage-detail-dialog"
    destroy-on-close
  >
    <template v-if="event">
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
        {{ t('admin.mindbot.usageEventDetailPrivacy') }}
      </p>
      <el-descriptions
        :column="1"
        border
        size="small"
        class="mindbot-usage-detail-desc"
      >
        <el-descriptions-item :label="t('admin.mindbot.detailId')">
          {{ event.id }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colTime')">
          {{ formatTime(event.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colError')">
          {{ event.error_code }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailStreaming')">
          {{ event.streaming ? t('admin.mindbot.detailYes') : t('admin.mindbot.detailNo') }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colDuration')">
          {{ formatDur(event.duration_seconds) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colStaff')">
          {{ event.sender_nick || event.dingtalk_staff_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailStaffId')">
          {{ event.dingtalk_staff_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailSenderOpenId')">
          {{ event.dingtalk_sender_id ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailDifyUserKey')">
          <span class="font-mono text-xs break-all">{{ event.dify_user_key }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colTurn')">
          {{ event.conversation_user_turn ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colScope')">
          {{ event.dingtalk_chat_scope ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailInboundType')">
          {{ event.inbound_msg_type ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colMsgId')">
          <span class="font-mono text-xs break-all">{{ event.msg_id ?? '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colDifyConv')">
          <span class="font-mono text-xs break-all">{{ event.dify_conversation_id ?? '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colDtConv')">
          <span class="font-mono text-xs break-all">{{ event.dingtalk_conversation_id ?? '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colChars')">
          {{ event.prompt_chars }} / {{ event.reply_chars }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.colTokens')">
          {{ formatTokens(event) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailOrgId')">
          {{ event.organization_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailConfigId')">
          {{ event.mindbot_config_id ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('admin.mindbot.detailLinkedUser')">
          {{ event.linked_user_id ?? '—' }}
        </el-descriptions-item>
      </el-descriptions>
    </template>
  </el-dialog>
</template>

<style scoped>
.mindbot-usage-detail-desc :deep(.el-descriptions__label) {
  width: 160px;
}
</style>
