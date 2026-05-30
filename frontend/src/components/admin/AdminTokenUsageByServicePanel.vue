<script setup lang="ts">
/**
 * Token usage by service (MindGraph / MindMate) — platform-wide or per-organization.
 */
import { computed, onMounted, ref, watch } from 'vue'

import AdminSwissServiceCard from '@/components/admin/swiss/AdminSwissServiceCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'
import { ChatDotRound, Connection, Loading, Refresh } from '@element-plus/icons-vue'

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
  today?: TokenPeriodStats
  past_week?: TokenPeriodStats
  past_month?: TokenPeriodStats
  total?: TokenPeriodStats
  by_service?: {
    mindgraph: ServiceStats
    mindmate: ServiceStats
  }
}

const props = withDefaults(
  defineProps<{
    /** When set, stats are scoped to this school; otherwise platform-wide. */
    organizationId?: number
    /** Use school manager endpoint (required for non-admin school dashboard). */
    useSchoolStatsEndpoint?: boolean
    /** When provided, panel uses parent data instead of fetching. */
    stats?: TokenStatsByService | null
    showOverallSummary?: boolean
    clickable?: boolean
  }>(),
  {
    organizationId: undefined,
    useSchoolStatsEndpoint: false,
    stats: undefined,
    showOverallSummary: false,
    clickable: false,
  }
)

const emit = defineEmits<{
  serviceClick: [service: 'mindgraph' | 'mindmate']
  overallClick: []
}>()

const { t } = useLanguage()
const notify = useNotifications()

const isLoading = ref(false)
const tokenStats = ref<TokenStatsByService | null>(null)

const usesExternalStats = computed(() => props.stats !== undefined)

const displayStats = computed(() =>
  usesExternalStats.value ? (props.stats ?? null) : tokenStats.value
)

const servicePeriods = [
  { key: 'today' as const, label: () => t('admin.today') },
  { key: 'week' as const, label: () => t('admin.thisWeek') },
  { key: 'month' as const, label: () => t('admin.thisMonth') },
  { key: 'total' as const, label: () => t('admin.allTime') },
]

const overallPeriods = [
  { key: 'today' as const, label: () => t('admin.today'), statsKey: 'today' as const },
  { key: 'week' as const, label: () => t('admin.pastWeek'), statsKey: 'past_week' as const },
  { key: 'month' as const, label: () => t('admin.pastMonth'), statsKey: 'past_month' as const },
  { key: 'total' as const, label: () => t('admin.allTime'), statsKey: 'total' as const },
]

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
    if (props.useSchoolStatsEndpoint) {
      return `/api/auth/admin/stats/school/token-stats?organization_id=${props.organizationId}`
    }
    return `/api/auth/admin/token-stats?organization_id=${props.organizationId}`
  }
  return '/api/auth/admin/token-stats'
}

function serviceStats(service: 'mindgraph' | 'mindmate', period: keyof ServiceStats): TokenPeriodStats {
  return (
    displayStats.value?.by_service?.[service]?.[period] ?? {
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      request_count: 0,
    }
  )
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

const hasData = computed(() => displayStats.value != null)

onMounted(() => {
  if (!usesExternalStats.value) {
    void loadTokenStats()
  }
})

watch(
  () => props.stats,
  (value) => {
    if (usesExternalStats.value) {
      tokenStats.value = value ?? null
    }
  },
  { immediate: true }
)

watch(
  () => [props.organizationId, props.useSchoolStatsEndpoint] as const,
  () => {
    if (usesExternalStats.value) {
      return
    }
    tokenStats.value = null
    void loadTokenStats()
  }
)

defineExpose({ loadTokenStats, hasData })
</script>

<template>
  <div class="admin-token-by-service">
    <div
      v-if="!usesExternalStats && isLoading"
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

    <template v-else-if="displayStats">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <AdminSwissServiceCard
          theme="mindgraph"
          :clickable="clickable"
          @click="emit('serviceClick', 'mindgraph')"
        >
          <template #header>
            <div class="flex items-center gap-3">
              <div class="swiss-stat-card__icon">
                <el-icon :size="20">
                  <Connection />
                </el-icon>
              </div>
              <div>
                <h3 class="swiss-stat-card__service-title">MindGraph</h3>
                <p class="text-xs text-[var(--swiss-muted)]">{{ t('admin.diagramGeneration') }}</p>
              </div>
            </div>
          </template>
          <div class="swiss-stat-card__stat-item-grid swiss-stat-card__stat-item-grid--pair">
            <div
              v-for="period in servicePeriods"
              :key="period.key"
              class="swiss-stat-card__stat-item"
            >
              <p class="swiss-stat-card__stat-item-k">{{ period.label() }}</p>
              <p class="swiss-stat-card__stat-item-v">
                {{ formatNumber(serviceStats('mindgraph', period.key).total_tokens) }}
              </p>
              <p class="swiss-stat-card__stat-item-sub">
                {{ (serviceStats('mindgraph', period.key).request_count || 0).toLocaleString() }}
                {{ t('admin.requests') }}
              </p>
            </div>
          </div>
          <div class="mt-4 pt-4 border-t border-[var(--swiss-border)]">
            <div class="flex justify-between text-sm">
              <span class="text-[var(--swiss-muted)]">{{ t('admin.inputTokens') }}</span>
              <span class="font-medium">
                {{ formatNumber(serviceStats('mindgraph', 'total').input_tokens) }}
              </span>
            </div>
            <div class="flex justify-between text-sm mt-1">
              <span class="text-[var(--swiss-muted)]">{{ t('admin.outputTokens') }}</span>
              <span class="font-medium">
                {{ formatNumber(serviceStats('mindgraph', 'total').output_tokens) }}
              </span>
            </div>
          </div>
        </AdminSwissServiceCard>

        <AdminSwissServiceCard
          theme="mindmate"
          :clickable="clickable"
          @click="emit('serviceClick', 'mindmate')"
        >
          <template #header>
            <div class="flex items-center gap-3">
              <div class="swiss-stat-card__icon">
                <el-icon :size="20">
                  <ChatDotRound />
                </el-icon>
              </div>
              <div>
                <h3 class="swiss-stat-card__service-title">MindMate</h3>
                <p class="text-xs text-[var(--swiss-muted)]">{{ t('admin.aiAssistant') }}</p>
              </div>
            </div>
          </template>
          <div class="swiss-stat-card__stat-item-grid swiss-stat-card__stat-item-grid--pair">
            <div
              v-for="period in servicePeriods"
              :key="period.key"
              class="swiss-stat-card__stat-item"
            >
              <p class="swiss-stat-card__stat-item-k">{{ period.label() }}</p>
              <p class="swiss-stat-card__stat-item-v">
                {{ formatNumber(serviceStats('mindmate', period.key).total_tokens) }}
              </p>
              <p class="swiss-stat-card__stat-item-sub">
                {{ (serviceStats('mindmate', period.key).request_count || 0).toLocaleString() }}
                {{ t('admin.requests') }}
              </p>
            </div>
          </div>
          <div class="mt-4 pt-4 border-t border-[var(--swiss-border)]">
            <div class="flex justify-between text-sm">
              <span class="text-[var(--swiss-muted)]">{{ t('admin.inputTokens') }}</span>
              <span class="font-medium">
                {{ formatNumber(serviceStats('mindmate', 'total').input_tokens) }}
              </span>
            </div>
            <div class="flex justify-between text-sm mt-1">
              <span class="text-[var(--swiss-muted)]">{{ t('admin.outputTokens') }}</span>
              <span class="font-medium">
                {{ formatNumber(serviceStats('mindmate', 'total').output_tokens) }}
              </span>
            </div>
          </div>
        </AdminSwissServiceCard>
      </div>

      <AdminSwissServiceCard
        v-if="showOverallSummary"
        theme="platform"
        class="mb-2"
        :clickable="clickable"
        @click="emit('overallClick')"
      >
        <template #header>
          <div class="flex items-center justify-between gap-2 w-full">
            <span class="swiss-stat-card__service-title">{{ t('admin.overallTokenSummary') }}</span>
            <el-button
              text
              size="small"
              @click.stop="loadTokenStats"
            >
              <el-icon class="mr-1"><Refresh /></el-icon>
              {{ t('common.refresh') }}
            </el-button>
          </div>
        </template>
        <div class="swiss-stat-card__stat-item-grid">
          <div
            v-for="period in overallPeriods"
            :key="period.key"
            class="swiss-stat-card__stat-item text-center"
          >
            <p class="swiss-stat-card__stat-item-k">{{ period.label() }}</p>
            <p class="swiss-stat-card__stat-item-v">
              {{ formatNumber(displayStats[period.statsKey]?.total_tokens || 0) }}
            </p>
            <p class="swiss-stat-card__stat-item-sub">
              {{ t('admin.inShort') }}:
              {{ formatNumber(displayStats[period.statsKey]?.input_tokens || 0) }}
              · {{ t('admin.outShort') }}:
              {{ formatNumber(displayStats[period.statsKey]?.output_tokens || 0) }}
            </p>
          </div>
        </div>
      </AdminSwissServiceCard>
    </template>
  </div>
</template>
