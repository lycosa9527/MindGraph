<script setup lang="ts">
/**
 * MaiteReportActions — export session report.
 */
import { ref } from 'vue'

import { getSessionReport } from '@/api/maite/reports'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'

const props = defineProps<{
  sessionId: number | null
}>()

const { t } = useLanguage()
const loading = ref(false)
const reportMarkdown = ref('')

async function loadReport(): Promise<void> {
  if (!props.sessionId) {
    return
  }
  loading.value = true
  try {
    eventBus.emit('maite:report_export_requested', { sessionId: props.sessionId })
    const report = await getSessionReport(props.sessionId)
    reportMarkdown.value = report.report_markdown ?? report.summary ?? ''
  } catch (error: unknown) {
    eventBus.emit('maite:error', {
      message: error instanceof Error ? error.message : 'report_failed',
      source: 'report_actions',
    })
  } finally {
    loading.value = false
  }
}

async function copyReport(): Promise<void> {
  if (!reportMarkdown.value) {
    await loadReport()
  }
  if (!reportMarkdown.value) {
    return
  }
  try {
    await navigator.clipboard.writeText(reportMarkdown.value)
    notify.success(t('notification.copied'))
  } catch {
    eventBus.emit('maite:error', {
      message: 'report_copy_failed',
      source: 'report_actions',
    })
  }
}
</script>

<template>
  <div v-if="sessionId" class="maite-report-actions">
    <button type="button" class="maite-report-actions__btn" :disabled="loading" @click="loadReport">
      {{ loading ? t('maite.report.loading') : t('maite.report.view') }}
    </button>
    <button
      type="button"
      class="maite-report-actions__btn maite-report-actions__btn--secondary"
      :disabled="loading"
      @click="copyReport"
    >
      {{ t('maite.report.copy') }}
    </button>
    <pre v-if="reportMarkdown" class="maite-report-actions__preview">{{ reportMarkdown }}</pre>
  </div>
</template>

<style scoped>
.maite-report-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.maite-report-actions__btn {
  align-self: flex-start;
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  background: #667eea;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}

.maite-report-actions__btn--secondary {
  background: var(--el-fill-color, #fafaf9);
  color: var(--el-text-color-primary, #1c1917);
  border: 1px solid var(--el-border-color, #e7e5e4);
}

.maite-report-actions__preview {
  max-height: 240px;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: var(--el-fill-color-lighter, #fafaf9);
  font-size: 12px;
  white-space: pre-wrap;
}
</style>
