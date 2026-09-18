<script setup lang="ts">
import { FileSearch } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables'
import type { AdminErrorEventItem } from '@/composables/queries/adminApi'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  event: (AdminErrorEventItem & { stacktrace?: string | null }) | null
}>()

const { t } = useLanguage()

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function formatTags(tags: Record<string, unknown> | null | undefined): string {
  if (!tags || Object.keys(tags).length === 0) {
    return '—'
  }
  try {
    return JSON.stringify(tags, null, 2)
  } catch {
    return '—'
  }
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
    width="min(620px, 92vw)"
    dialog-class="admin-error-detail-dialog"
  >
    <template v-if="props.event">
      <div
        class="admin-error-detail-scroll max-h-[min(72vh,640px)] overflow-y-auto overflow-x-hidden pr-0.5"
      >
        <p class="text-xs text-[var(--swiss-muted)] mb-3">
          <I18nText k="admin.errors.detailPrivacy" />
        </p>
        <el-descriptions
          :column="1"
          border
          size="small"
          class="admin-error-detail-desc w-full max-w-full"
        >
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.detailId" />
            </template>
            <span class="font-mono text-xs break-all">{{ props.event.id }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.time" />
            </template>
            {{ formatTime(props.event.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.severity" />
            </template>
            <span class="font-mono text-xs uppercase">{{ props.event.severity }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.source" />
            </template>
            <span class="font-mono text-xs">{{ props.event.source }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.component" />
            </template>
            <span class="font-mono text-xs break-all">{{ props.event.component }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.type" />
            </template>
            <span class="font-mono text-xs break-all">{{ props.event.exception_type }}</span>
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.fingerprint" />
            </template>
            <span class="font-mono text-xs break-all">{{ props.event.fingerprint }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="props.event.http_path">
            <template #label>
              <I18nText k="admin.errors.path" />
            </template>
            <span class="font-mono text-xs break-all">{{ props.event.http_path }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="props.event.http_status != null">
            <template #label>
              <I18nText k="admin.errors.httpStatus" />
            </template>
            {{ props.event.http_status }}
          </el-descriptions-item>
          <el-descriptions-item v-if="props.event.request_id">
            <template #label>
              <I18nText k="admin.errors.requestId" />
            </template>
            <span class="font-mono text-xs break-all">{{ props.event.request_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="props.event.user_id != null">
            <template #label>
              <I18nText k="admin.errors.userId" />
            </template>
            {{ props.event.user_id }}
          </el-descriptions-item>
          <el-descriptions-item>
            <template #label>
              <I18nText k="admin.errors.message" />
            </template>
            <pre class="admin-error-detail-pre">{{ props.event.message }}</pre>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="props.event.tags && Object.keys(props.event.tags).length > 0"
            :label="t('admin.errors.tags')"
          >
            <pre class="admin-error-detail-pre">{{ formatTags(props.event.tags) }}</pre>
          </el-descriptions-item>
          <el-descriptions-item v-if="props.event.stacktrace">
            <template #label>
              <I18nText k="admin.errors.stacktrace" />
            </template>
            <pre class="admin-error-detail-pre admin-error-detail-pre--stack">{{
              props.event.stacktrace
            }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.admin-error-detail-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.45;
  max-height: 200px;
  overflow: auto;
}

.admin-error-detail-pre--stack {
  max-height: 280px;
}
</style>
