<script setup lang="ts">
/**
 * Token usage chart + period summary cards (user modal — Usage tab).
 */
import { ref } from 'vue'

import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import { Loading } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'

defineProps<{
  chartLoading: boolean
  chartHasData: boolean
  period: 'today' | 'week' | 'month' | 'total'
  periodCards: { today: string; week: string; month: string; total: string }
}>()

const emit = defineEmits<{
  (e: 'switchPeriod', p: 'today' | 'week' | 'month' | 'total'): void
}>()

const { t } = useLanguage()

const chartRef = ref<HTMLCanvasElement | null>(null)

defineExpose({ chartRef })
</script>

<template>
  <div class="user-token-tab space-y-4">
    <div
      v-if="chartLoading"
      class="flex justify-center items-center h-56"
    >
      <el-icon
        class="is-loading text-[var(--swiss-muted)]"
        :size="32"
      >
        <Loading />
      </el-icon>
    </div>
    <template v-else>
      <div
        v-if="!chartHasData"
        class="flex justify-center items-center h-56 text-gray-500 dark:text-gray-400"
      >
        {{ t('admin.trendChartNoData') }}
      </div>
      <template v-else>
      <div class="relative h-56 min-h-[220px] w-full min-w-0">
        <canvas
          ref="chartRef"
          class="block w-full h-full"
        />
      </div>
      <div class="grid grid-cols-1 min-[400px]:grid-cols-2 lg:grid-cols-4 gap-3">
        <AdminSwissPeriodCard
          :label="t('admin.today')"
          :value="periodCards.today"
          :active="period === 'today'"
          theme="storage"
          @click="emit('switchPeriod', 'today')"
        />
        <AdminSwissPeriodCard
          :label="t('admin.pastWeek')"
          :value="periodCards.week"
          :active="period === 'week'"
          theme="storage"
          @click="emit('switchPeriod', 'week')"
        />
        <AdminSwissPeriodCard
          :label="t('admin.pastMonth')"
          :value="periodCards.month"
          :active="period === 'month'"
          theme="storage"
          @click="emit('switchPeriod', 'month')"
        />
        <AdminSwissPeriodCard
          :label="t('admin.allTime')"
          :value="periodCards.total"
          :active="period === 'total'"
          theme="storage"
          @click="emit('switchPeriod', 'total')"
        />
      </div>
      </template>
    </template>
  </div>
</template>
