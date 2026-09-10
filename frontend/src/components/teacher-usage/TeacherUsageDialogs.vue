<script setup lang="ts">
/**
 * Teacher usage: classification config + teacher list modal and user detail modal.
 */
import { inject, watch } from 'vue'

import { Loading } from '@element-plus/icons-vue'

import { BarChart3, Loader2 } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import type { Teacher } from '@/composables/teacherUsage/teacherUsageTypes'
import { teacherUsageInjectionKey } from '@/composables/teacherUsage/useTeacherUsagePage'

const injected = inject(teacherUsageInjectionKey)
if (!injected) {
  throw new Error('TeacherUsageDialogs must be used on TeacherUsagePage')
}

const {
  t,
  showTeachersModal,
  modalTitle,
  modalTeachers,
  modalStatCardType,
  configForm,
  isSavingConfig,
  isRecomputing,
  saveConfig,
  recomputeClassifications,
  formatNumber,
  openUserChart,
  showUserChartModal,
  selectedUser,
  userChartLoading,
  userDetailData,
  closeUserChartModal,
  onUserChartModalOpened,
  userChartRef,
} = injected

watch(showUserChartModal, (isOpen) => {
  if (isOpen) {
    onUserChartModalOpened()
  }
})
</script>

<template>
  <!-- Teachers list modal -->
  <SwissGlassDialog
    v-model="showTeachersModal"
    :ribbon="t('swissGlass.hero.teacherUsage.ribbon')"
    :title="t('swissGlass.hero.teacherUsage.title')"
    :line1="t('swissGlass.hero.teacherUsage.line1')"
    :icon="BarChart3"
    width="min(700px, 92vw)"
  >
    <p
      v-if="modalTitle"
      class="text-sm font-medium text-stone-700 mb-3"
    >
      {{ modalTitle }}
    </p>
    <!-- Classification rules (for non-total): show only rules for the selected category -->
    <div
      v-if="modalStatCardType && modalStatCardType !== 'total'"
      class="mb-4 pb-4 border-b border-stone-200"
    >
      <h4 class="text-sm font-semibold text-stone-700 mb-3">
        {{ t('teacher.analytics.rulesTitle') }}
      </h4>
      <!-- 未使用: active_days = 0 (fixed, read-only) -->
      <div
        v-if="modalStatCardType === 'unused'"
        class="text-sm text-stone-600"
      >
        <code class="bg-stone-100 px-2 py-1 rounded">{{
          t('teacher.analytics.ruleUnusedLine')
        }}</code>
        <span class="ml-2">{{ t('teacher.analytics.ruleUnusedHint') }}</span>
      </div>
      <!-- 持续使用 -->
      <el-form
        v-else-if="modalStatCardType === 'continuous'"
        label-position="top"
        class="grid grid-cols-2 md:grid-cols-4 gap-3"
      >
        <el-form-item :label="t('teacher.analytics.form.activeWeeks')">
          <el-input-number
            v-model="configForm.continuous.active_weeks_min"
            :min="1"
            :max="20"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.activeWeeksFirst4')">
          <el-input-number
            v-model="configForm.continuous.active_weeks_first4_min"
            :min="0"
            :max="4"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.activeWeeksLast4')">
          <el-input-number
            v-model="configForm.continuous.active_weeks_last4_min"
            :min="0"
            :max="4"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.maxZeroGapMax')">
          <el-input-number
            v-model="configForm.continuous.max_zero_gap_days_max"
            :min="1"
            :max="56"
            size="small"
          />
        </el-form-item>
      </el-form>
      <!-- 拒绝使用 -->
      <el-form
        v-else-if="modalStatCardType === 'rejection'"
        label-position="top"
        class="grid grid-cols-2 md:grid-cols-4 gap-3"
      >
        <el-form-item :label="t('teacher.analytics.form.activeDaysMax')">
          <el-input-number
            v-model="configForm.rejection.active_days_max"
            :min="0"
            :max="10"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.activeDaysFirst10')">
          <el-input-number
            v-model="configForm.rejection.active_days_first10_min"
            :min="0"
            :max="10"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.activeDaysLast25')">
          <el-input-number
            v-model="configForm.rejection.active_days_last25_max"
            :min="0"
            :max="25"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.maxZeroGapMinRej')">
          <el-input-number
            v-model="configForm.rejection.max_zero_gap_days_min"
            :min="1"
            :max="56"
            size="small"
          />
        </el-form-item>
      </el-form>
      <!-- 停止使用 -->
      <el-form
        v-else-if="modalStatCardType === 'stopped'"
        label-position="top"
        class="grid grid-cols-2 md:grid-cols-3 gap-3"
      >
        <el-form-item :label="t('teacher.analytics.form.activeDaysFirst25')">
          <el-input-number
            v-model="configForm.stopped.active_days_first25_min"
            :min="0"
            :max="25"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.activeDaysLast14')">
          <el-input-number
            v-model="configForm.stopped.active_days_last14_max"
            :min="0"
            :max="14"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.maxZeroGapMinStop')">
          <el-input-number
            v-model="configForm.stopped.max_zero_gap_days_min"
            :min="1"
            :max="56"
            size="small"
          />
        </el-form-item>
      </el-form>
      <!-- 间歇式使用 -->
      <el-form
        v-else-if="modalStatCardType === 'intermittent'"
        label-position="top"
        class="grid grid-cols-2 gap-3"
      >
        <el-form-item :label="t('teacher.analytics.form.nBursts')">
          <el-input-number
            v-model="configForm.intermittent.n_bursts_min"
            :min="1"
            :max="10"
            size="small"
          />
        </el-form-item>
        <el-form-item :label="t('teacher.analytics.form.internalMaxGap')">
          <el-input-number
            v-model="configForm.intermittent.internal_max_zero_gap_days_min"
            :min="1"
            :max="56"
            size="small"
          />
        </el-form-item>
      </el-form>
      <div
        v-if="modalStatCardType !== 'unused'"
        class="flex gap-2 mt-2"
      >
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
          :disabled="isSavingConfig"
          @click="saveConfig"
        >
          <Loader2
            v-if="isSavingConfig"
            class="w-3.5 h-3.5 animate-spin"
          />
          {{ t('teacher.analytics.saveOnly') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary"
          :disabled="isRecomputing"
          @click="recomputeClassifications"
        >
          <Loader2
            v-if="isRecomputing"
            class="w-3.5 h-3.5 animate-spin"
          />
          {{ t('teacher.analytics.saveRecompute') }}
        </button>
      </div>
    </div>
    <el-table
      :data="modalTeachers"
      stripe
      size="small"
      max-height="400"
      class="teachers-table-clickable"
      @row-click="(row: Teacher) => openUserChart(row)"
    >
      <el-table-column
        prop="username"
        :label="t('teacher.analytics.colTeacher')"
        width="160"
      />
      <el-table-column
        prop="diagrams"
        :label="t('teacher.analytics.colAutocompleteCount')"
        width="90"
      />
      <el-table-column
        prop="conceptGen"
        :label="t('teacher.analytics.colConceptGen')"
        width="90"
      />
      <el-table-column
        prop="relationshipLabels"
        :label="t('teacher.analytics.colRelLabels')"
        width="90"
      />
      <el-table-column
        prop="tokens"
        :label="t('teacher.analytics.colTokens')"
        width="100"
      >
        <template #default="{ row }">
          {{ formatNumber(row.tokens) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="lastActive"
        :label="t('teacher.analytics.colLastActive')"
      />
    </el-table>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="showTeachersModal = false"
        >
          {{ t('common.close') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>

  <!-- User detail modal: chart (3 numbers) + token tracking cards -->
  <SwissGlassDialog
    v-model="showUserChartModal"
    :ribbon="t('swissGlass.hero.teacherUsage.ribbon')"
    :title="t('swissGlass.hero.teacherUsage.title')"
    :line1="t('swissGlass.hero.teacherUsage.line1')"
    :icon="BarChart3"
    width="min(640px, 92vw)"
    @close="closeUserChartModal"
  >
    <p
      v-if="selectedUser"
      class="text-sm font-medium text-stone-700 mb-3"
    >
      {{ selectedUser.username }}
    </p>
    <div
      v-if="userChartLoading"
      class="flex items-center justify-center py-12"
    >
      <el-icon
        class="is-loading"
        :size="24"
        ><Loading
      /></el-icon>
    </div>
    <template v-else>
      <div
        ref="userChartRef"
        class="user-chart-container mb-6"
      />
      <div
        v-if="userDetailData"
        class="grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        <el-card
          shadow="hover"
          class="token-stat-card"
        >
          <p class="text-xs text-gray-500 mb-1">
            {{ t('common.date.today') }}
          </p>
          <p class="text-lg font-semibold">
            {{ formatNumber(userDetailData.tokenStats.today.total_tokens) }}
          </p>
        </el-card>
        <el-card
          shadow="hover"
          class="token-stat-card"
        >
          <p class="text-xs text-gray-500 mb-1">
            {{ t('teacher.analytics.periodWeek') }}
          </p>
          <p class="text-lg font-semibold">
            {{ formatNumber(userDetailData.tokenStats.week.total_tokens) }}
          </p>
        </el-card>
        <el-card
          shadow="hover"
          class="token-stat-card"
        >
          <p class="text-xs text-gray-500 mb-1">
            {{ t('teacher.analytics.periodMonth') }}
          </p>
          <p class="text-lg font-semibold">
            {{ formatNumber(userDetailData.tokenStats.month.total_tokens) }}
          </p>
        </el-card>
        <el-card
          shadow="hover"
          class="token-stat-card"
        >
          <p class="text-xs text-gray-500 mb-1">
            {{ t('teacher.analytics.periodTotal') }}
          </p>
          <p class="text-lg font-semibold">
            {{ formatNumber(userDetailData.tokenStats.total.total_tokens) }}
          </p>
        </el-card>
      </div>
    </template>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="closeUserChartModal"
        >
          {{ t('common.close') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.user-chart-container {
  width: 100%;
  min-height: 256px;
  height: 256px;
}
</style>
