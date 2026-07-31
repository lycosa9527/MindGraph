<script setup lang="ts">
/**
 * MaiteInquiryView — full inquiry workflow with stage rail.
 */
import { onMounted, watch } from 'vue'

import MaiteDiagnosisPanel from '@/components/maite/inquiry/MaiteDiagnosisPanel.vue'
import MaiteRemedyPanel from '@/components/maite/inquiry/MaiteRemedyPanel.vue'
import MaiteStageRail from '@/components/maite/inquiry/MaiteStageRail.vue'
import MaiteTablesEditor from '@/components/maite/inquiry/MaiteTablesEditor.vue'
import MaiteVariantPanel from '@/components/maite/inquiry/MaiteVariantPanel.vue'
import MaiteProblemInput from '@/components/maite/shared/MaiteProblemInput.vue'
import MaiteReportActions from '@/components/maite/shared/MaiteReportActions.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMaiteInquiry } from '@/composables/maite/useMaiteInquiry'
import { useMaiteStore } from '@/stores/maite'

import type { MaiteInquiryStage } from '@/types/maite'

const { t } = useLanguage()
const store = useMaiteStore()

const {
  loading,
  errorMessage,
  activeStage,
  tables,
  diagnosisResult,
  remedyTasks,
  variantTasks,
  studentThinking,
  readOnlyPhases,
  decomposeReadonly,
  canComplete,
  sessionId,
  loadSnapshot,
  startInquirySession,
  submitDecomposeTables,
  runDiagnoseAuto,
  runRemedyGenerate,
  runVariantsGenerate,
  submitVariantAnswer,
  completeInquiry,
  selectStage,
} = useMaiteInquiry()

onMounted(async () => {
  if (store.activeSessionId) {
    await loadSnapshot(store.activeSessionId)
  }
})

watch(
  () => store.activeSessionId,
  async (nextSessionId) => {
    if (nextSessionId) {
      await loadSnapshot(nextSessionId)
    }
  }
)

async function startSession(): Promise<void> {
  const text = store.currentProblemText.trim()
  if (!text) {
    return
  }
  await startInquirySession(text)
}

function onProblemUpdate(value: string): void {
  store.setCurrentProblemText(value)
}

function onStageSelect(stage: MaiteInquiryStage): void {
  selectStage(stage)
}
</script>

<template>
  <div class="maite-inquiry-view">
    <MaiteStageRail
      :active-stage="activeStage"
      :read-only-phases="readOnlyPhases"
      @select="onStageSelect"
    />

    <section v-if="!sessionId" class="maite-inquiry-view__section">
      <h3 class="maite-inquiry-view__heading">{{ t('maite.inquiry.startTitle') }}</h3>
      <MaiteProblemInput
        :model-value="store.currentProblemText"
        scene="question"
        :disabled="loading"
        @update:model-value="onProblemUpdate"
      />
      <button
        type="button"
        class="maite-inquiry-view__btn"
        :disabled="loading || !store.currentProblemText.trim()"
        @click="startSession"
      >
        {{ loading ? t('maite.inquiry.starting') : t('maite.inquiry.start') }}
      </button>
    </section>

    <template v-else>
      <section v-if="activeStage === 'decompose'" class="maite-inquiry-view__section">
        <h3 class="maite-inquiry-view__heading">{{ t('maite.inquiry.decomposeTitle') }}</h3>
        <MaiteTablesEditor
          :condition-table="tables.condition_table"
          :step-table="tables.step_table"
          :model-table="tables.model_table"
          :readonly="decomposeReadonly"
          @update:condition-table="(rows) => (tables.condition_table = rows)"
          @update:step-table="(rows) => (tables.step_table = rows)"
          @update:model-table="(rows) => (tables.model_table = rows)"
        />
        <button
          v-if="!decomposeReadonly"
          type="button"
          class="maite-inquiry-view__btn"
          :disabled="loading"
          @click="submitDecomposeTables"
        >
          {{ t('maite.inquiry.submitDecompose') }}
        </button>
      </section>

      <section v-else-if="activeStage === 'diagnosis'" class="maite-inquiry-view__section">
        <h3 class="maite-inquiry-view__heading">{{ t('maite.inquiry.diagnosisTitle') }}</h3>
        <MaiteDiagnosisPanel
          v-model:student-thinking="studentThinking"
          :loading="loading"
          :result="diagnosisResult"
          @run-auto="runDiagnoseAuto"
        />
      </section>

      <section v-else-if="activeStage === 'remedy'" class="maite-inquiry-view__section">
        <h3 class="maite-inquiry-view__heading">{{ t('maite.inquiry.remedyTitle') }}</h3>
        <MaiteRemedyPanel
          :tasks="remedyTasks"
          :loading="loading"
          @generate="runRemedyGenerate"
        />
      </section>

      <section v-else-if="activeStage === 'variant'" class="maite-inquiry-view__section">
        <h3 class="maite-inquiry-view__heading">{{ t('maite.inquiry.variantTitle') }}</h3>
        <MaiteVariantPanel
          :tasks="variantTasks"
          :loading="loading"
          :can-complete="canComplete"
          @generate="runVariantsGenerate"
          @complete="completeInquiry"
          @submit="submitVariantAnswer"
        />
      </section>

      <section v-else class="maite-inquiry-view__section">
        <h3 class="maite-inquiry-view__heading">{{ t('maite.inquiry.completedTitle') }}</h3>
        <p>{{ t('maite.inquiry.completedMessage') }}</p>
        <MaiteReportActions :session-id="sessionId" />
      </section>
    </template>

    <p v-if="errorMessage" class="maite-inquiry-view__error">
      {{ t(`maite.errors.${errorMessage}`, errorMessage) }}
    </p>
  </div>
</template>

<style scoped>
.maite-inquiry-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.maite-inquiry-view__section {
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
}

.maite-inquiry-view__heading {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}

.maite-inquiry-view__btn {
  margin-top: 10px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: #667eea;
  color: #fff;
  cursor: pointer;
}

.maite-inquiry-view__error {
  margin: 0;
  color: #dc2626;
  font-size: 13px;
}
</style>
