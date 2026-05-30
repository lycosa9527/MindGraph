<script setup lang="ts">
/**
 * Token usage by service (MindGraph / MindMate) — platform-wide or per-organization.
 */
import { onMounted, ref, watch } from 'vue'

import { ChatDotRound, Connection, Loading } from '@element-plus/icons-vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

interface TokenPeriodStats {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  request_count?: number
}

interface ServiceStats {
  today: TokenPeriodStats
  week: TokenPeriodStats
  month: TokenPeriodStats
  total: TokenPeriodStats
}

interface TokenStatsByService {
  by_service?: {
    mindgraph: ServiceStats
    mindmate: ServiceStats
  }
}

const props = defineProps<{
  /** When set, stats are scoped to this school; otherwise platform-wide. */
  organizationId?: number
}>()

const { t } = useLanguage()
const notify = useNotifications()

const isLoading = ref(false)
const tokenStats = ref<TokenStatsByService | null>(null)

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`
  }
  return num.toLocaleString()
}

function statsEndpoint(): string {
  if (props.organizationId != null) {
    return `/api/auth/admin/token-stats?organization_id=${props.organizationId}`
  }
  return '/api/auth/admin/token-stats'
}

async function loadTokenStats(): Promise<void> {
  if (isLoading.value) {
    return
  }
  isLoading.value = true
  try {
    const response = await apiRequest(statsEndpoint())
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.tokenStatsLoadError'))
      return
    }
    tokenStats.value = await response.json()
  } catch {
    notify.error(t('admin.tokenStatsNetworkError'))
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  void loadTokenStats()
})

watch(
  () => props.organizationId,
  () => {
    tokenStats.value = null
    void loadTokenStats()
  }
)
</script>

<template>
  <div class="admin-token-by-service">
    <div
      v-if="isLoading"
      class="text-center py-12"
    >
      <el-icon
        class="is-loading"
        :size="32"
      >
        <Loading />
      </el-icon>
      <p class="mt-4 text-gray-500">{{ t('admin.loadingTokenStats') }}</p>
    </div>

    <template v-else-if="tokenStats">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <el-card
          shadow="hover"
          class="service-card mindgraph-card"
        >
          <template #header>
            <div class="flex items-center gap-3">
              <div
                class="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center"
              >
                <el-icon
                  :size="20"
                  class="text-blue-500"
                >
                  <Connection />
                </el-icon>
              </div>
              <div>
                <h3 class="font-semibold text-gray-800 dark:text-white">MindGraph</h3>
                <p class="text-xs text-gray-500">{{ t('admin.diagramGeneration') }}</p>
              </div>
            </div>
          </template>
          <div class="grid grid-cols-2 gap-4">
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.today') }}</p>
              <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                {{ formatNumber(tokenStats.by_service?.mindgraph?.today?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindgraph?.today?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisWeek') }}</p>
              <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                {{ formatNumber(tokenStats.by_service?.mindgraph?.week?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindgraph?.week?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisMonth') }}</p>
              <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                {{ formatNumber(tokenStats.by_service?.mindgraph?.month?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindgraph?.month?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.allTime') }}</p>
              <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindgraph?.total?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
          </div>
          <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
            <div class="flex justify-between text-sm">
              <span class="text-gray-500">{{ t('admin.inputTokens') }}</span>
              <span class="font-medium text-gray-700 dark:text-gray-300">
                {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.input_tokens || 0) }}
              </span>
            </div>
            <div class="flex justify-between text-sm mt-1">
              <span class="text-gray-500">{{ t('admin.outputTokens') }}</span>
              <span class="font-medium text-gray-700 dark:text-gray-300">
                {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.output_tokens || 0) }}
              </span>
            </div>
          </div>
        </el-card>

        <el-card
          shadow="hover"
          class="service-card mindmate-card"
        >
          <template #header>
            <div class="flex items-center gap-3">
              <div
                class="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center"
              >
                <el-icon
                  :size="20"
                  class="text-purple-500"
                >
                  <ChatDotRound />
                </el-icon>
              </div>
              <div>
                <h3 class="font-semibold text-gray-800 dark:text-white">MindMate</h3>
                <p class="text-xs text-gray-500">{{ t('admin.aiAssistant') }}</p>
              </div>
            </div>
          </template>
          <div class="grid grid-cols-2 gap-4">
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.today') }}</p>
              <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                {{ formatNumber(tokenStats.by_service?.mindmate?.today?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindmate?.today?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisWeek') }}</p>
              <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                {{ formatNumber(tokenStats.by_service?.mindmate?.week?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindmate?.week?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisMonth') }}</p>
              <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                {{ formatNumber(tokenStats.by_service?.mindmate?.month?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindmate?.month?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
            <div class="stat-item">
              <p class="text-xs text-gray-500 mb-1">{{ t('admin.allTime') }}</p>
              <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                {{ formatNumber(tokenStats.by_service?.mindmate?.total?.total_tokens || 0) }}
              </p>
              <p class="text-xs text-gray-400">
                {{
                  (tokenStats.by_service?.mindmate?.total?.request_count || 0).toLocaleString()
                }}
                {{ t('admin.requests') }}
              </p>
            </div>
          </div>
          <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
            <div class="flex justify-between text-sm">
              <span class="text-gray-500">{{ t('admin.inputTokens') }}</span>
              <span class="font-medium text-gray-700 dark:text-gray-300">
                {{ formatNumber(tokenStats.by_service?.mindmate?.total?.input_tokens || 0) }}
              </span>
            </div>
            <div class="flex justify-between text-sm mt-1">
              <span class="text-gray-500">{{ t('admin.outputTokens') }}</span>
              <span class="font-medium text-gray-700 dark:text-gray-300">
                {{ formatNumber(tokenStats.by_service?.mindmate?.total?.output_tokens || 0) }}
              </span>
            </div>
          </div>
        </el-card>
      </div>
    </template>
  </div>
</template>

<style scoped src="@/styles/admin-token-by-service.css"></style>
