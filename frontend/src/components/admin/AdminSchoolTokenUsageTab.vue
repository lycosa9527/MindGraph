<script setup lang="ts">
/**
 * Token usage chart + period summary cards (school modal — Usage tab).
 */
import { ref } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'

defineProps<{
  chartLoading: boolean
  period: 'today' | 'week' | 'month' | 'total'
  periodCards: { today: string; week: string; month: string; total: string }
}>()

const emit = defineEmits<{
  (e: 'switch-period', p: 'today' | 'week' | 'month' | 'total'): void
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
        class="is-loading text-[var(--mindbot-swiss-muted)]"
        :size="32"
      >
        <Loading />
      </el-icon>
    </div>
    <template v-else>
      <div class="relative h-56 min-h-[220px] w-full min-w-0">
        <canvas
          ref="chartRef"
          class="block w-full h-full"
        />
      </div>
      <div class="grid grid-cols-1 min-[400px]:grid-cols-2 gap-3">
        <button
          v-for="item in [
            { key: 'today' as const, label: t('admin.today'), value: periodCards.today },
            { key: 'week' as const, label: t('admin.pastWeek'), value: periodCards.week },
            { key: 'month' as const, label: t('admin.pastMonth'), value: periodCards.month },
            { key: 'total' as const, label: t('admin.allTime'), value: periodCards.total },
          ]"
          :key="item.key"
          type="button"
          class="school-token-period-card text-left"
          :class="{ 'school-token-period-card--active': period === item.key }"
          @click="emit('switch-period', item.key)"
        >
          <p class="school-token-period-card__label">{{ item.label }}</p>
          <p class="school-token-period-card__value">{{ item.value }}</p>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.school-token-period-card {
  padding: 12px 14px;
  border-radius: 4px;
  border: 1px solid var(--mindbot-swiss-border, rgba(34, 211, 238, 0.32));
  background: var(--mindbot-swiss-inset, rgba(15, 23, 42, 0.72));
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
  cursor: pointer;
}

.school-token-period-card:hover {
  border-color: rgba(34, 211, 238, 0.55);
}

.school-token-period-card--active {
  border-color: #22d3ee;
  box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.35);
}

.school-token-period-card__label {
  margin: 0 0 4px;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--mindbot-swiss-muted, #a8b7c9);
}

.school-token-period-card__value {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--mindbot-swiss-text, #f1f5f9);
}
</style>
