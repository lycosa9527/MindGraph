<script setup lang="ts">
import { computed } from 'vue'

import type { AdminErrorEventItem } from '@/composables/queries/adminApi'
import { useLanguage } from '@/composables'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  event: (AdminErrorEventItem & { stacktrace?: string | null }) | null
}>()

const { t } = useLanguage()

const title = computed(() => t('admin.errors.detailTitle'))

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
  <el-dialog
    v-model="visible"
    :title="title"
    width="min(620px, 92vw)"
    class="admin-error-detail-dialog"
    append-to-body
    align-center
    destroy-on-close
  >
    <template v-if="props.event">
      <div
        class="admin-error-detail-scroll max-h-[min(72vh,640px)] overflow-y-auto overflow-x-hidden pr-0.5"
      >
        <p class="text-xs text-[var(--swiss-muted)] mb-3">
          {{ t('admin.errors.detailPrivacy') }}
        </p>
        <el-descriptions
          :column="1"
          border
          size="small"
          class="admin-error-detail-desc w-full max-w-full"
        >
          <el-descriptions-item :label="t('admin.errors.detailId')">
            <span class="font-mono text-xs break-all">{{ props.event.id }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('admin.errors.time')">
            {{ formatTime(props.event.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('admin.errors.severity')">
            <span class="font-mono text-xs uppercase">{{ props.event.severity }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('admin.errors.source')">
            <span class="font-mono text-xs">{{ props.event.source }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('admin.errors.component')">
            <span class="font-mono text-xs break-all">{{ props.event.component }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('admin.errors.type')">
            <span class="font-mono text-xs break-all">{{ props.event.exception_type }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('admin.errors.fingerprint')">
            <span class="font-mono text-xs break-all">{{ props.event.fingerprint }}</span>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="props.event.http_path"
            :label="t('admin.errors.path')"
          >
            <span class="font-mono text-xs break-all">{{ props.event.http_path }}</span>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="props.event.http_status != null"
            :label="t('admin.errors.httpStatus')"
          >
            {{ props.event.http_status }}
          </el-descriptions-item>
          <el-descriptions-item
            v-if="props.event.request_id"
            :label="t('admin.errors.requestId')"
          >
            <span class="font-mono text-xs break-all">{{ props.event.request_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="props.event.user_id != null"
            :label="t('admin.errors.userId')"
          >
            {{ props.event.user_id }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('admin.errors.message')">
            <pre class="admin-error-detail-pre">{{ props.event.message }}</pre>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="props.event.tags && Object.keys(props.event.tags).length > 0"
            :label="t('admin.errors.tags')"
          >
            <pre class="admin-error-detail-pre">{{ formatTags(props.event.tags) }}</pre>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="props.event.stacktrace"
            :label="t('admin.errors.stacktrace')"
          >
            <pre class="admin-error-detail-pre admin-error-detail-pre--stack">{{
              props.event.stacktrace
            }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </template>
  </el-dialog>
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
