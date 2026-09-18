<script setup lang="ts">
import { FileSearch } from '@lucide/vue'

import type { MindbotUsageEventRow } from '@/components/admin/mindbotUsageTypes'
import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables'

const visible = defineModel<boolean>({ required: true })

defineProps<{
  event: MindbotUsageEventRow | null
}>()

const { t } = useLanguage()

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
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('swissGlass.hero.adminEvent.ribbon')"
    ribbon-key="swissGlass.hero.adminEvent.ribbon"
    :title="t('swissGlass.hero.adminEvent.title')"
    title-key="swissGlass.hero.adminEvent.title"
    :line1="t('swissGlass.hero.adminEvent.line1')"
    line1-key="swissGlass.hero.adminEvent.line1"
    :icon="FileSearch"
    width="min(560px, 92vw)"
    dialog-class="mindbot-usage-detail-dialog"
  >
    <template v-if="event">
      <div
        class="mindbot-usage-detail-scroll max-h-[min(70vh,560px)] overflow-y-auto overflow-x-hidden pr-0.5"
      >
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
          <I18nText k="admin.mindbot.usageEventDetailPrivacy" />
        </p>
        <el-descriptions
          :column="1"
          border
          size="small"
          class="mindbot-usage-detail-desc w-full max-w-full"
        >
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailId" />
            </template>
            <span class="font-mono text-xs break-all">{{ event.id }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colTime" />
            </template>
            {{ formatTime(event.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colError" />
            </template>
            {{ event.error_code }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailStreaming" />
            </template>
            <I18nText :k="event.streaming ? 'admin.mindbot.detailYes' : 'admin.mindbot.detailNo'" />
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colDuration" />
            </template>
            {{ formatDur(event.duration_seconds) }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colStaff" />
            </template>
            {{ event.sender_nick || event.dingtalk_staff_id }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailStaffId" />
            </template>
            {{ event.dingtalk_staff_id }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailSenderOpenId" />
            </template>
            {{ event.dingtalk_sender_id ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailDifyUserKey" />
            </template>
            <span class="font-mono text-xs break-all">{{ event.dify_user_key }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colTurn" />
            </template>
            {{ event.conversation_user_turn ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colScope" />
            </template>
            {{ event.dingtalk_chat_scope ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailInboundType" />
            </template>
            {{ event.inbound_msg_type ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colMsgId" />
            </template>
            <span class="font-mono text-xs break-all">{{ event.msg_id ?? '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colDifyConv" />
            </template>
            <span class="font-mono text-xs break-all">{{ event.dify_conversation_id ?? '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colDtConv" />
            </template>
            <span class="font-mono text-xs break-all">{{
              event.dingtalk_conversation_id ?? '—'
            }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colChars" />
            </template>
            {{ event.prompt_chars }} / {{ event.reply_chars }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.colTokens" />
            </template>
            {{ formatTokens(event) }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailOrgId" />
            </template>
            {{ event.organization_id }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailConfigId" />
            </template>
            {{ event.mindbot_config_id ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.mindbot.detailLinkedUser" />
            </template>
            {{ event.linked_user_id ?? '—' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.mindbot-usage-detail-desc :deep(.el-descriptions__label) {
  width: 9.5rem;
  max-width: 42%;
  vertical-align: top;
}
.mindbot-usage-detail-desc :deep(.el-descriptions__content) {
  min-width: 0;
  word-break: break-word;
}
.mindbot-usage-detail-desc :deep(table) {
  table-layout: fixed;
  width: 100%;
}
</style>
