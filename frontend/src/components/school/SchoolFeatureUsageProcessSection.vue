<script setup lang="ts">
import { computed } from 'vue'

import AdminSwissModuleStatCard from '@/components/admin/swiss/AdminSwissModuleStatCard.vue'
import type {
  SchoolFeatureUsageBottleneckSlots,
  SchoolFeatureUsageModule,
} from '@/composables/queries/adminSchoolFeatureUsageApi'
import { useLanguage } from '@/composables'
import { moduleUsageTheme } from '@/utils/schoolFeatureUsageTheme'

const props = defineProps<{
  modules: SchoolFeatureUsageModule[]
  bottleneck: SchoolFeatureUsageBottleneckSlots
  timestamp: string
}>()

const { t } = useLanguage()

function moduleTitle(key: string): string {
  return t(`admin.schoolFeatureUsage.module.${key}`)
}

function joinNames(keys: string[]): string {
  if (keys.length === 0) {
    return t('admin.schoolFeatureUsage.noneListed')
  }
  return keys.map((key) => moduleTitle(key)).join(t('admin.schoolFeatureUsage.nameSep'))
}

function passLabel(value: number): string {
  return `${value.toFixed(1)}%`
}

function failLabel(value: number | null): string {
  if (value == null) {
    return '—'
  }
  return `${value.toFixed(1)}%`
}

function durationLabel(seconds: number | null): string {
  if (seconds == null) {
    return '—'
  }
  if (seconds >= 60) {
    return t('admin.schoolFeatureUsage.durationMin', { value: (seconds / 60).toFixed(1) })
  }
  return t('admin.schoolFeatureUsage.durationSec', { value: seconds.toFixed(1) })
}

function processChips(row: SchoolFeatureUsageModule) {
  const chips = [
    { label: t('admin.schoolFeatureUsage.passRate'), value: passLabel(row.pass_rate) },
  ]
  if (row.fail_rate != null) {
    chips.push({
      label: t('admin.schoolFeatureUsage.llmFailRate'),
      value: failLabel(row.fail_rate),
    })
  }
  chips.push(
    {
      label: t('admin.schoolFeatureUsage.llmDuration'),
      value: durationLabel(row.avg_duration_seconds),
    },
    {
      label: t('admin.schoolFeatureUsage.capacity'),
      value: t(`admin.schoolFeatureUsage.capacity.${row.capacity}`),
    }
  )
  return chips
}

const bottleneckText = computed(() => {
  const slots = props.bottleneck
  if (slots.no_bottleneck) {
    return t('admin.schoolFeatureUsage.bottleneckNone')
  }
  const slow = joinNames(slots.slow_keys)
  if (slots.uniformly_high && slots.slow_keys.length > 0) {
    return t('admin.schoolFeatureUsage.bottleneckSlow', { slow })
  }
  if (slots.uniformly_high) {
    const idleKeys = props.modules.filter((row) => row.uses === 0).map((row) => row.key)
    return t('admin.schoolFeatureUsage.bottleneckVolume', {
      idle: joinNames(idleKeys),
    })
  }
  if (slots.slow_keys.length > 0) {
    return t('admin.schoolFeatureUsage.bottleneckPassSlow', {
      lowest: joinNames(slots.lowest_pass_keys),
      tense: joinNames(slots.tense_keys),
      slow,
    })
  }
  return t('admin.schoolFeatureUsage.bottleneckPass', {
    lowest: joinNames(slots.lowest_pass_keys),
    tense: joinNames(slots.tense_keys),
  })
})
</script>

<template>
  <section class="school-activity-section">
    <h2 class="school-activity-section__title">
      {{ t('admin.schoolFeatureUsage.sectionProcess') }}
    </h2>
    <div class="school-activity-section__grid">
      <AdminSwissModuleStatCard
        v-for="row in props.modules"
        :key="row.key"
        :title="moduleTitle(row.key)"
        :value="row.completed"
        :value-label="t('admin.schoolFeatureUsage.completed')"
        :timestamp="props.timestamp"
        :theme="moduleUsageTheme(row.key)"
        :chips="processChips(row)"
        :empty="row.avg_duration_seconds == null"
        :empty-text="t('admin.schoolFeatureUsage.durationEmpty')"
      />
    </div>
    <p class="school-feature-usage-brief">
      {{ bottleneckText }}
    </p>
  </section>
</template>

<style scoped>
.school-feature-usage-brief {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  line-height: 1.6;
  color: #44403c;
}
</style>
