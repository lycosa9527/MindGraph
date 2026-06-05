<script setup lang="ts">
/**
 * Platform token overview — overall usage summary and DingTalk generation card.
 */
import { computed, ref, watch } from 'vue'

import { Key, Refresh } from '@element-plus/icons-vue'

import AdminDingtalkGenerationApiKeysDialog from '@/components/admin/AdminDingtalkGenerationApiKeysDialog.vue'
import AdminSwissServiceCard from '@/components/admin/swiss/AdminSwissServiceCard.vue'
import { useLanguage } from '@/composables'
import { useAdminApiKeys } from '@/composables/queries'

interface TokenPeriodStats {
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

interface TokenStats {
  today: TokenPeriodStats
  past_week: TokenPeriodStats
  past_month: TokenPeriodStats
  total: TokenPeriodStats
}

const props = withDefaults(
  defineProps<{
    tokenStats: TokenStats
    showDingtalk?: boolean
    clickable?: boolean
  }>(),
  {
    showDingtalk: false,
    clickable: false,
  }
)

const emit = defineEmits<{
  overallClick: []
  periodClick: [period: 'today' | 'week' | 'month' | 'total']
  refresh: []
}>()

const { t } = useLanguage()

const dingtalkApiKeysDialogVisible = ref(false)

const apiKeysQuery = useAdminApiKeys()

const dingtalkKeyUsesTotal = computed(() => {
  const list = apiKeysQuery.data.value
  if (!list) {
    return null
  }
  return list.reduce((acc, row) => acc + (row.usage_count ?? 0), 0)
})

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

function onPeriodClick(period: 'today' | 'week' | 'month' | 'total', event: MouseEvent): void {
  if (!props.clickable) {
    return
  }
  event.stopPropagation()
  emit('periodClick', period)
}

function openDingtalkApiKeysDialog(): void {
  dingtalkApiKeysDialogVisible.value = true
}

watch(dingtalkApiKeysDialogVisible, (open) => {
  if (!open) {
    void apiKeysQuery.refetch()
  }
})

watch(
  () => props.showDingtalk,
  (show) => {
    if (show) {
      void apiKeysQuery.refetch()
    }
  },
  { immediate: true }
)

function onDingtalkCardKeydown(e: KeyboardEvent): void {
  if (e.key !== 'Enter' && e.key !== ' ') {
    return
  }
  e.preventDefault()
  openDingtalkApiKeysDialog()
}
</script>

<template>
  <div
    class="grid grid-cols-1 gap-6 mb-2 items-stretch"
    :class="showDingtalk ? 'lg:grid-cols-3' : ''"
  >
    <AdminSwissServiceCard
      theme="platform"
      class="overall-token-row h-full min-h-0"
      :class="showDingtalk ? 'lg:col-span-2' : ''"
      :clickable="clickable"
      @click="emit('overallClick')"
    >
      <template #header>
        <div
          class="flex items-center justify-between w-full"
          @click.stop
        >
          <span class="swiss-stat-card__service-title">{{ t('admin.overallTokenSummary') }}</span>
          <el-button
            text
            size="small"
            @click="emit('refresh')"
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
          @click="onPeriodClick(period.key, $event)"
        >
          <p class="swiss-stat-card__stat-item-k">{{ period.label() }}</p>
          <p class="swiss-stat-card__stat-item-v">
            {{ formatNumber(tokenStats[period.statsKey]?.total_tokens || 0) }}
          </p>
          <p class="swiss-stat-card__stat-item-sub">
            {{ t('admin.inShort') }}:
            {{ formatNumber(tokenStats[period.statsKey]?.input_tokens || 0) }}
            · {{ t('admin.outShort') }}:
            {{ formatNumber(tokenStats[period.statsKey]?.output_tokens || 0) }}
          </p>
        </div>
      </div>
    </AdminSwissServiceCard>

    <AdminSwissServiceCard
      v-if="showDingtalk"
      theme="integration"
      class="h-full min-h-0"
      clickable
      focusable
      :aria-label="`${t('admin.dingtalkGenerationCard')}. ${t('admin.dingtalkCardClickToEditApiKeys')}`"
      @click="openDingtalkApiKeysDialog"
      @keydown="onDingtalkCardKeydown"
    >
      <template #header>
        <div class="flex min-h-0 items-center gap-2">
          <div class="swiss-stat-card__icon">
            <el-icon :size="16">
              <Key />
            </el-icon>
          </div>
          <p class="swiss-stat-card__service-title">
            {{ t('admin.dingtalkGenerationCard') }}
          </p>
        </div>
      </template>
      <div class="dingtalk-generation-body">
        <p
          class="text-xl font-semibold tabular-nums sm:text-2xl"
          style="color: var(--stat-accent)"
        >
          <template v-if="dingtalkKeyUsesTotal !== null">
            {{ t('admin.dingtalkCardTotalUses', { count: dingtalkKeyUsesTotal }) }}
          </template>
          <template v-else>—</template>
        </p>
        <p class="text-center text-xs leading-snug text-[var(--swiss-muted)]">
          {{ t('admin.dingtalkCardClickToEditApiKeys') }}
        </p>
      </div>
    </AdminSwissServiceCard>
  </div>

  <AdminDingtalkGenerationApiKeysDialog v-model="dingtalkApiKeysDialogVisible" />
</template>

<style scoped src="@/styles/admin-token-by-service.css"></style>
