<script setup lang="ts">
/**
 * Super-admin school dashboard — 用户活跃度分析.
 */
import { computed, ref, watch } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import SchoolActivityActiveSection from '@/components/school/SchoolActivityActiveSection.vue'
import SchoolActivityFrequencySection from '@/components/school/SchoolActivityFrequencySection.vue'
import SchoolActivityTotalsSection from '@/components/school/SchoolActivityTotalsSection.vue'
import { useLanguage } from '@/composables'
import { useAdminSchoolUserActivityQuery } from '@/composables/queries/useAdminSchoolUserActivityQuery'
import { queryErrorMessage } from '@/composables/admin/useQueryErrorNotification'
import { beijingCalendarYear, formatBeijingSnapshotTime } from '@/utils/schoolActivityAsOf'

const props = defineProps<{
  orgId: number
}>()

const { t } = useLanguage()
const selectedYear = ref(beijingCalendarYear())

const query = useAdminSchoolUserActivityQuery(
  computed(() => props.orgId),
  selectedYear
)

const payload = computed(() => query.data.value ?? null)
const isPending = computed(() => query.isPending.value)
const isError = computed(() => query.isError.value)
const loadError = computed(() =>
  queryErrorMessage(query.error.value, t('admin.schoolActivity.loadError'))
)
const minYear = computed(() => payload.value?.min_year ?? selectedYear.value)
const maxYear = computed(() => beijingCalendarYear())
const yearOptions = computed(() => {
  const years: number[] = []
  for (let year = maxYear.value; year >= minYear.value; year -= 1) {
    years.push(year)
  }
  return years
})

const timestamp = computed(() => {
  const iso = payload.value?.generated_at
  if (!iso) {
    return ''
  }
  return t('admin.schoolActivity.asOf', { time: formatBeijingSnapshotTime(iso) })
})

watch(
  () => payload.value?.min_year,
  (lowest) => {
    if (lowest != null && selectedYear.value < lowest) {
      selectedYear.value = lowest
    }
  }
)
</script>

<template>
  <div class="school-activity-tab">
    <div class="school-activity-tab__toolbar">
      <label class="school-activity-tab__year">
        <span>{{ t('admin.schoolActivity.year') }}</span>
        <el-select
          v-model="selectedYear"
          class="admin-swiss-select"
          size="small"
        >
          <el-option
            v-for="year in yearOptions"
            :key="year"
            :label="String(year)"
            :value="year"
          />
        </el-select>
      </label>
    </div>

    <div
      v-if="isPending"
      class="flex justify-center py-20"
    >
      <el-icon
        class="is-loading"
        :size="32"
      >
        <Loading />
      </el-icon>
    </div>

    <p
      v-else-if="isError"
      class="school-activity-tab__error"
    >
      {{ loadError }}
    </p>

    <template v-else-if="payload">
      <SchoolActivityTotalsSection
        :totals="payload.totals"
        :timestamp="timestamp"
      />
      <SchoolActivityActiveSection
        :activity="payload.activity"
        :timestamp="timestamp"
      />
      <SchoolActivityFrequencySection
        :frequency="payload.frequency"
        :timestamp="timestamp"
      />
    </template>
  </div>
</template>

<style scoped>
.school-activity-tab {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  padding-top: 0.5rem;
}

.school-activity-tab__toolbar {
  display: flex;
  justify-content: flex-end;
}

.school-activity-tab__year {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8125rem;
  color: #57534e;
}

.school-activity-tab__error {
  margin: 2rem 0;
  text-align: center;
  color: #b45309;
}

.school-activity-tab :deep(.school-activity-section__title) {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  font-weight: 600;
  color: #1c1917;
}

.school-activity-tab :deep(.school-activity-section__grid) {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1.25rem;
}

@media (min-width: 768px) {
  .school-activity-tab :deep(.school-activity-section__grid) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
