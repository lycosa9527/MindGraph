<script setup lang="ts">
/**
 * Token usage chart + period summary cards (school modal — Usage tab).
 */
import { ref } from 'vue'

import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import { Loading } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'

defineProps<{
  chartLoading: boolean
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
  <div class="school-token-tab space-y-4">
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
      <div class="school-modal-chart-panel relative h-60 min-h-[240px] w-full min-w-0">
        <canvas
          ref="chartRef"
          class="block w-full h-full"
        />
      </div>
      <div class="grid grid-cols-1 min-[400px]:grid-cols-2 gap-3">
        <AdminSwissPeriodCard
          v-for="item in [
            { key: 'today' as const, label: t('admin.today'), value: periodCards.today },
            { key: 'week' as const, label: t('admin.pastWeek'), value: periodCards.week },
            { key: 'month' as const, label: t('admin.pastMonth'), value: periodCards.month },
            { key: 'total' as const, label: t('admin.allTime'), value: periodCards.total },
          ]"
          :key="item.key"
          :label="item.label"
          :value="item.value"
          :active="period === item.key"
          theme="storage"
          @click="emit('switchPeriod', item.key)"
        />
      </div>
    </template>
  </div>
</template>
