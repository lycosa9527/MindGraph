<script setup lang="ts">
/**
 * Org-scoped token trend dialog — chart + synced period summary cards.
 */
import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import { Loading } from '@element-plus/icons-vue'

import {
  useOrgTokenTrendModal,
  type TokenTrendPeriod,
  type TokenTrendService,
} from '@/composables/admin/useOrgTokenTrendModal'
import { useLanguage } from '@/composables'

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
  <el-dialog
    :model-value="trendModalVisible"
    :title="trendChartTitle"
    width="640px"
    destroy-on-close
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
      <el-button @click="closeTrendModal">{{ t('common.close') }}</el-button>
    </template>
  </el-dialog>
</template>
