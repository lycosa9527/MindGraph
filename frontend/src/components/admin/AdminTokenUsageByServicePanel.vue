<script setup lang="ts">
/**
 * Token usage by service (MindGraph / MindMate) — platform-wide or per-organization.
 */
import { computed, onMounted, watch } from 'vue'

import AdminSwissServiceCard from '@/components/admin/swiss/AdminSwissServiceCard.vue'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useLanguage, useNotifications } from '@/composables'
import {
  useAdminSchoolTokenStats,
  useAdminTokenStats,
} from '@/composables/queries'
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
  periodClick: [service: 'mindgraph' | 'mindmate' | null, period: 'today' | 'week' | 'month' | 'total']
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { on: onAdminEvent } = useAdminEventBus('AdminTokenUsageByServicePanel')

const usesExternalStats = computed(() => props.stats !== undefined)

const orgIdRef = computed(() => props.organizationId ?? null)

const platformTokenQuery = useAdminTokenStats(orgIdRef, {
  enabled: computed(() => !usesExternalStats.value && !props.useSchoolStatsEndpoint),
})

const schoolTokenQuery = useAdminSchoolTokenStats(orgIdRef, {
  enabled: computed(
    () =>
      !usesExternalStats.value &&
      props.useSchoolStatsEndpoint &&
      props.organizationId != null
  ),
})

const activeQuery = computed(() =>
  props.useSchoolStatsEndpoint ? schoolTokenQuery : platformTokenQuery
)

const isLoading = computed(() => activeQuery.value.isFetching.value)
const tokenStats = computed(() => (activeQuery.value.data.value as TokenStatsByService | undefined) ?? null)

const displayStats = computed(() =>
  usesExternalStats.value ? (props.stats ?? null) : tokenStats.value
)

const servicePeriods = [
  { key: 'today' as const, label: () => t('admin.today') },
  { key: 'week' as const, label: () => t('admin.pastWeek') },
  { key: 'month' as const, label: () => t('admin.pastMonth') },
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

function onPeriodClick(
  service: 'mindgraph' | 'mindmate' | null,
  period: 'today' | 'week' | 'month' | 'total',
  event: MouseEvent
): void {
  if (!props.clickable) {
    return
  }
  event.stopPropagation()
  emit('periodClick', service, period)
}

function onServiceCardClick(service: 'mindgraph' | 'mindmate'): void {
  if (!props.clickable) {
    return
  }
  emit('serviceClick', service)
}

function onOverallCardClick(): void {
  if (!props.clickable) {
    return
  }
  emit('overallClick')
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
  try {
    await activeQuery.value.refetch()
  } catch (err) {
    const message = err instanceof Error ? err.message : t('admin.tokenStatsNetworkError')
    notify.error(message || t('admin.tokenStatsNetworkError'))
  }
}

const hasData = computed(() => displayStats.value != null)

onAdminEvent('admin:refresh_requested', ({ domain }) => {
  if (usesExternalStats.value) {
    return
  }
  if (domain === 'token-stats' || domain === 'stats' || domain === 'all') {
    void loadTokenStats()
  }
})

onMounted(() => {
  if (!usesExternalStats.value) {
    void loadTokenStats()
  }
})

watch(
  () => [props.organizationId, props.useSchoolStatsEndpoint] as const,
  () => {
    if (usesExternalStats.value) {
      return
    }
    void loadTokenStats()
  }
)
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

    <template v-else-if="!usesExternalStats && activeQuery.isError.value">
      <div class="text-center py-12 text-gray-500 dark:text-gray-400">
        <p>{{ t('admin.tokenStatsLoadError') }}</p>
        <el-button
          class="mt-4"
          size="small"
          @click="loadTokenStats()"
        >
          {{ t('common.refresh') }}
        </el-button>
      </div>
    </template>

    <template v-else-if="displayStats">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <AdminSwissServiceCard
          theme="mindgraph"
          :clickable="clickable"
          @click="onServiceCardClick('mindgraph')"
        >
          <template #header>
            <div class="flex items-center gap-3">
              <div class="swiss-stat-card__icon">
                <el-icon :size="20">
                  <Connection />
                </el-icon>
              </div>
              <div>
                <h3 class="swiss-stat-card__service-title">{{ t('admin.serviceMindGraph') }}</h3>
                <p class="text-xs text-[var(--swiss-muted)]">{{ t('admin.diagramGeneration') }}</p>
              </div>
            </div>
          </template>
          <div class="swiss-stat-card__stat-item-grid swiss-stat-card__stat-item-grid--pair">
            <div
              v-for="period in servicePeriods"
              :key="period.key"
              class="swiss-stat-card__stat-item"
              :class="{ 'swiss-stat-card__stat-item--clickable': clickable }"
              @click="onPeriodClick('mindgraph', period.key, $event)"
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
          @click="onServiceCardClick('mindmate')"
        >
          <template #header>
            <div class="flex items-center gap-3">
              <div class="swiss-stat-card__icon">
                <el-icon :size="20">
                  <ChatDotRound />
                </el-icon>
              </div>
              <div>
                <h3 class="swiss-stat-card__service-title">{{ t('admin.serviceMindMate') }}</h3>
                <p class="text-xs text-[var(--swiss-muted)]">{{ t('admin.aiAssistant') }}</p>
              </div>
            </div>
          </template>
          <div class="swiss-stat-card__stat-item-grid swiss-stat-card__stat-item-grid--pair">
            <div
              v-for="period in servicePeriods"
              :key="period.key"
              class="swiss-stat-card__stat-item"
              :class="{ 'swiss-stat-card__stat-item--clickable': clickable }"
              @click="onPeriodClick('mindmate', period.key, $event)"
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
        @click="onOverallCardClick"
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
            :class="{ 'swiss-stat-card__stat-item--clickable': clickable }"
            @click="onPeriodClick(null, period.key, $event)"
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
