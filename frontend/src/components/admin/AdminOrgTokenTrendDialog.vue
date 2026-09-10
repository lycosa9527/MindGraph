<script setup lang="ts">
/**
 * Org-scoped token trend dialog — chart + synced period summary cards.
 */
import { Loading } from '@element-plus/icons-vue'

import { TrendingUp } from '@lucide/vue'

import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables'
import {
  type TokenTrendPeriod,
  type TokenTrendService,
  useOrgTokenTrendModal,
} from '@/composables/admin/useOrgTokenTrendModal'

const { t } = useLanguage()

const {
  trendModalVisible,
  trendChartTitle,
  trendChartLoading,
  trendChartHasData,
  trendChartRef,
  periodCards,
  trendPeriod,
  showTrendChart,
  switchTrendPeriod,
  closeTrendModal,
} = useOrgTokenTrendModal()

export interface OpenOrgTokenTrendOptions {
  orgId?: number
  orgName: string
  period?: TokenTrendPeriod
  service?: TokenTrendService
  useSchoolStatsEndpoint?: boolean
}

function openTrend(options: OpenOrgTokenTrendOptions): void {
  void showTrendChart(options)
}

function onDialogVisibleChange(visible: boolean): void {
  if (!visible) {
    closeTrendModal()
  }
}

defineExpose({
  openTrend,
  closeTrendModal,
})
</script>

<template>
  <SwissGlassDialog
    :model-value="trendModalVisible"
    :ribbon="t('swissGlass.hero.adminOrgTrend.ribbon')"
    :title="t('swissGlass.hero.adminOrgTrend.title')"
    :line1="t('swissGlass.hero.adminOrgTrend.line1')"
    :line2="trendChartTitle"
    :icon="TrendingUp"
    width="640px"
    @update:model-value="onDialogVisibleChange"
    @close="closeTrendModal"
  >
    <div
      v-if="trendChartLoading"
      class="flex justify-center items-center h-64"
    >
      <el-icon
        class="is-loading"
        :size="32"
      >
        <Loading />
      </el-icon>
    </div>
    <template v-else>
      <div
        v-if="!trendChartHasData"
        class="flex justify-center items-center h-64 text-gray-500 dark:text-gray-400"
      >
        {{ t('admin.trendChartNoData') }}
      </div>
      <div
        v-else
        class="relative h-64 min-h-[256px] w-full"
      >
        <canvas
          ref="trendChartRef"
          class="block w-full h-full"
        />
      </div>
      <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <AdminSwissPeriodCard
            :label="t('admin.today')"
            :value="periodCards.today"
            :active="trendPeriod === 'today'"
            theme="storage"
            @click="switchTrendPeriod('today')"
          />
          <AdminSwissPeriodCard
            :label="t('admin.pastWeek')"
            :value="periodCards.week"
            :active="trendPeriod === 'week'"
            theme="storage"
            @click="switchTrendPeriod('week')"
          />
          <AdminSwissPeriodCard
            :label="t('admin.pastMonth')"
            :value="periodCards.month"
            :active="trendPeriod === 'month'"
            theme="storage"
            @click="switchTrendPeriod('month')"
          />
          <AdminSwissPeriodCard
            :label="t('admin.allTime')"
            :value="periodCards.total"
            :active="trendPeriod === 'total'"
            theme="storage"
            @click="switchTrendPeriod('total')"
          />
        </div>
      </div>
    </template>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="closeTrendModal"
        >
          {{ t('common.close') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
