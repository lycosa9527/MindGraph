<script setup lang="ts">
/**
 * School modal — curated activity timeline for one organization.
 */
import { computed, ref, watch } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useScopedAbort } from '@/composables/core/useScopedAbort'
import {
  fetchAdminOrgActivity,
  type AdminOrgActivityItem,
} from '@/composables/queries/adminApi'
import { useUIStore } from '@/stores/ui'
import {
  activitySourceLabel,
  formatAdminUserActivitySummary,
  type ActivitySummaryLabels,
} from '@/utils/adminUserActivitySummary'

const props = defineProps<{
  orgId: number | null | undefined
  canLoad: boolean
}>()

type SourceFilter = 'all' | 'mindgraph' | 'mindmate' | 'dingtalk'

const { t } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()
const { beginRequest, abort: abortActivityRequests } = useScopedAbort()

const sourceFilter = ref<SourceFilter>('all')
const items = ref<AdminOrgActivityItem[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const beforeId = ref<number | null>(null)
const hasMore = ref(true)

const sourceFilterOptions = computed(() => [
  { label: t('admin.orgActivityTab.filterAll'), value: 'all' as const },
  { label: t('admin.orgActivityTab.filterMindgraph'), value: 'mindgraph' as const },
  { label: t('admin.orgActivityTab.filterMindmate'), value: 'mindmate' as const },
  { label: t('admin.orgActivityTab.filterDingtalk'), value: 'dingtalk' as const },
])

const summaryLabels = computed<ActivitySummaryLabels>(() => ({
  ask: t('admin.orgActivityTab.askPrefix'),
  answer: t('admin.orgActivityTab.answerPrefix'),
  generate: t('admin.orgActivityTab.generate'),
  save: t('admin.orgActivityTab.save'),
  dingtalkGenerate: t('admin.orgActivityTab.dingtalkGenerate'),
  sourceMindgraph: t('admin.orgActivityTab.sourceMindgraph'),
  sourceMindmate: t('admin.orgActivityTab.sourceMindmate'),
  sourceDingtalk: t('admin.orgActivityTab.sourceDingtalk'),
  failedSuffix: t('admin.orgActivityTab.failedSuffix'),
}))

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function rowSummary(row: AdminOrgActivityItem): string {
  return formatAdminUserActivitySummary(row, summaryLabels.value, uiStore.language)
}

function sourceBadge(row: AdminOrgActivityItem): string {
  return activitySourceLabel(row.source, summaryLabels.value)
}

function formatTokens(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return '—'
  }
  return String(value)
}

function userLabel(row: AdminOrgActivityItem): string {
  const name = row.userName?.trim()
  return name || `#${row.userId}`
}

async function loadPage(append: boolean): Promise<void> {
  const orgId = props.orgId
  if (orgId == null || orgId <= 0 || !props.canLoad) {
    return
  }
  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }
  try {
    const signal = beginRequest()
    const params: Record<string, string | number | undefined> = { limit: 50 }
    if (sourceFilter.value !== 'all') {
      params.source = sourceFilter.value
    }
    if (append && beforeId.value != null) {
      params.before_id = beforeId.value
    }
    const data = await fetchAdminOrgActivity(orgId, params, signal)
    const batch = data.items ?? []
    if (append) {
      items.value = [...items.value, ...batch]
    } else {
      items.value = batch
    }
    hasMore.value = Boolean(data.hasMore)
    beforeId.value = batch.length > 0 ? batch[batch.length - 1].id : null
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return
    }
    notify.error(t('admin.orgActivityTab.loadError'))
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function resetAndLoad(): void {
  items.value = []
  beforeId.value = null
  hasMore.value = true
  void loadPage(false)
}

watch(
  () => [props.orgId, props.canLoad] as const,
  ([orgId, canLoad]) => {
    abortActivityRequests()
    if (orgId != null && orgId > 0 && canLoad) {
      resetAndLoad()
    } else {
      items.value = []
    }
  },
  { immediate: true }
)

watch(sourceFilter, () => {
  if (props.canLoad && props.orgId != null) {
    resetAndLoad()
  }
})
</script>

<template>
  <div class="org-activity-tab space-y-3">
    <div class="org-activity-tab-toolbar">
      <p class="org-activity-tab-notice">
        {{ t('admin.orgActivityTab.privacyNotice') }}
      </p>
      <AdminSwissSegmented
        v-model="sourceFilter"
        class="org-activity-tab-filter"
        :options="sourceFilterOptions"
        fit
        :aria-label="t('admin.orgActivityTab.colProduct')"
      />
    </div>

    <div
      v-if="loading"
      class="flex justify-center items-center h-40"
    >
      <el-icon
        class="is-loading"
        :size="28"
      >
        <Loading />
      </el-icon>
    </div>

    <div
      v-else-if="items.length === 0"
      class="flex justify-center items-center h-40 text-gray-500 dark:text-gray-400 text-sm"
    >
      {{ t('admin.orgActivityTab.empty') }}
    </div>

    <div
      v-else
      class="overflow-x-auto"
    >
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-left text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th class="py-2 pr-3 font-medium whitespace-nowrap">
              {{ t('admin.orgActivityTab.colTime') }}
            </th>
            <th class="py-2 pr-3 font-medium whitespace-nowrap">
              {{ t('admin.orgActivityTab.colUser') }}
            </th>
            <th class="py-2 pr-3 font-medium whitespace-nowrap">
              {{ t('admin.orgActivityTab.colProduct') }}
            </th>
            <th class="py-2 pr-3 font-medium min-w-[12rem]">
              {{ t('admin.orgActivityTab.colSummary') }}
            </th>
            <th class="py-2 font-medium whitespace-nowrap text-right">
              {{ t('admin.orgActivityTab.colTokens') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in items"
            :key="row.id"
            class="border-b border-gray-100 dark:border-gray-800 align-top"
          >
            <td class="py-2 pr-3 whitespace-nowrap text-xs text-gray-600 dark:text-gray-300">
              {{ formatTime(row.createdAt) }}
            </td>
            <td class="py-2 pr-3 whitespace-nowrap text-xs text-gray-700 dark:text-gray-200">
              {{ userLabel(row) }}
            </td>
            <td class="py-2 pr-3 whitespace-nowrap">
              <span
                class="inline-block text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200"
              >
                {{ sourceBadge(row) }}
              </span>
            </td>
            <td class="py-2 pr-3 text-gray-800 dark:text-gray-100 break-words">
              {{ rowSummary(row) }}
            </td>
            <td class="py-2 whitespace-nowrap text-right text-xs text-gray-600 dark:text-gray-300">
              {{ formatTokens(row.totalTokens) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="hasMore && items.length > 0 && !loading"
      class="flex justify-center pt-2"
    >
      <el-button
        size="small"
        :loading="loadingMore"
        @click="loadPage(true)"
      >
        {{ t('admin.orgActivityTab.loadMore') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.org-activity-tab-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem 1rem;
}

.org-activity-tab-notice {
  flex: 1 1 12rem;
  min-width: 0;
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.45;
  color: var(--swiss-muted, #78716c);
}

.org-activity-tab-filter {
  flex: 0 0 auto;
  margin-left: auto;
}
</style>
