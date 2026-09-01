<script setup lang="ts">
import { computed } from 'vue'

import type { SchoolFeatureUsageJudgement } from '@/composables/queries/adminSchoolFeatureUsageApi'
import { useLanguage } from '@/composables'

const props = defineProps<{
  judgement: SchoolFeatureUsageJudgement
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

function rateLabel(rate: number | null): string {
  if (rate == null) {
    return '—'
  }
  return `${rate.toFixed(1)}%`
}

const conclusionText = computed(() => {
  const slots = props.judgement.conclusion_slots
  const concentrateKey = slots.concentrated
    ? 'admin.schoolFeatureUsage.conclusionConcentrated'
    : 'admin.schoolFeatureUsage.conclusionSpread'
  return t(concentrateKey, {
    top: joinNames(slots.top_keys),
    idle: joinNames(slots.idle_keys),
  })
})
</script>

<template>
  <section class="school-activity-section">
    <h2 class="school-activity-section__title">
      {{ t('admin.schoolFeatureUsage.sectionJudge') }}
    </h2>
    <ol class="school-feature-usage-judge">
      <li>
        <h3>{{ t('admin.schoolFeatureUsage.top5Title') }}</h3>
        <p v-if="props.judgement.top5.length === 0">
          {{ t('admin.schoolFeatureUsage.top5Empty') }}
        </p>
        <ol
          v-else
          class="school-feature-usage-rank"
        >
          <li
            v-for="(row, index) in props.judgement.top5"
            :key="row.key"
          >
            {{ index + 1 }}. {{ moduleTitle(row.key) }}
            — {{ t('admin.schoolFeatureUsage.usageRate') }} {{ rateLabel(row.usage_rate) }}
          </li>
        </ol>
        <p class="school-feature-usage-hint">
          {{ t('admin.schoolFeatureUsage.usageRateHint') }}
        </p>
      </li>
      <li>
        <h3>{{ t('admin.schoolFeatureUsage.highTitle') }}</h3>
        <p>{{ joinNames(props.judgement.high) }}</p>
      </li>
      <li>
        <h3>{{ t('admin.schoolFeatureUsage.lowIdleTitle') }}</h3>
        <p>
          {{ t('admin.schoolFeatureUsage.lowIdleBody', {
            low: joinNames(props.judgement.low),
            idle: joinNames(props.judgement.idle),
          }) }}
        </p>
      </li>
      <li>
        <h3>{{ t('admin.schoolFeatureUsage.conclusionTitle') }}</h3>
        <p>{{ conclusionText }}</p>
      </li>
    </ol>
    <p
      class="swiss-stat-card__hint"
      data-testid="school-feature-usage-judge-stamp"
    >
      {{ timestamp }}
    </p>
  </section>
</template>

<style scoped>
.school-feature-usage-judge {
  margin: 0;
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  color: #1c1917;
}

.school-feature-usage-judge h3 {
  margin: 0 0 0.35rem;
  font-size: 0.9375rem;
  font-weight: 600;
}

.school-feature-usage-judge p {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.6;
  color: #44403c;
}

.school-feature-usage-rank {
  margin: 0;
  padding-left: 0;
  list-style: none;
  font-size: 0.875rem;
  line-height: 1.6;
}

.school-feature-usage-hint {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: #78716c;
}

.swiss-stat-card__hint {
  margin: 1rem 0 0;
  font-size: 0.75rem;
  color: #78716c;
}
</style>
