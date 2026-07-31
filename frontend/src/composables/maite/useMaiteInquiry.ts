/**
 * Maite inquiry flow — stage rail, snapshot, diagnosis, remedy, variants, complete.
 */
import { computed, ref } from 'vue'

import {
  completeSession,
  getSnapshot,
  submitDecompose,
} from '@/api/maite/inquiry'
import { persistMaitePractice } from '@/composables/maite/useMaitePracticePersist'
import { diagnoseAuto, diagnoseFinalize } from '@/api/maite/diagnosis'
import { generateRemedyTasks } from '@/api/maite/remedy'
import { generateVariantTasks, submitVariantTask } from '@/api/maite/variants'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'
import { useMaiteStore } from '@/stores/maite'

import type {
  MaiteInquiryStage,
  MaiteRemedyTask,
  MaiteSessionSnapshot,
  MaiteTableRow,
  MaiteVariantTask,
} from '@/types/maite'

const STAGE_ORDER: MaiteInquiryStage[] = [
  'decompose',
  'diagnosis',
  'remedy',
  'variant',
  'completed',
]

function emptyTables(): {
  condition_table: MaiteTableRow[]
  step_table: MaiteTableRow[]
  model_table: MaiteTableRow[]
} {
  return {
    condition_table: [{ content: '' }],
    step_table: [{ content: '' }],
    model_table: [{ content: '' }],
  }
}

export function useMaiteInquiry() {
  const store = useMaiteStore()
  const { t } = useLanguage()

  const loading = ref(false)
  const errorMessage = ref('')
  const snapshot = ref<MaiteSessionSnapshot | null>(null)
  const activeStage = ref<MaiteInquiryStage>('decompose')
  const tables = ref(emptyTables())
  const diagnosisResult = ref<Record<string, unknown> | null>(null)
  const remedyTasks = ref<MaiteRemedyTask[]>([])
  const variantTasks = ref<MaiteVariantTask[]>([])
  const studentThinking = ref('')

  const readOnlyPhases = computed(() => {
    const currentIndex = STAGE_ORDER.indexOf(activeStage.value)
    return STAGE_ORDER.slice(0, Math.max(0, currentIndex))
  })

  const canComplete = computed(() => {
    const submitted = variantTasks.value.filter((task) => task.status === 'submitted').length
    return submitted >= 3
  })

  const sessionId = computed(() => store.activeSessionId)

  const decomposeReadonly = computed(() => readOnlyPhases.value.includes('decompose'))

  function syncStageFromSnapshot(data: MaiteSessionSnapshot): void {
    const stage = String(data.session?.current_stage ?? 'decompose') as MaiteInquiryStage
    activeStage.value = STAGE_ORDER.includes(stage) ? stage : 'decompose'
    eventBus.emit('maite:stage_changed', {
      sessionId: Number(data.session?.id ?? store.activeSessionId ?? 0),
      stage: activeStage.value,
      readOnlyPhases: readOnlyPhases.value,
    })
  }

  async function loadSnapshot(id = store.activeSessionId): Promise<void> {
    if (!id) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      const data = await getSnapshot(id)
      snapshot.value = data
      syncStageFromSnapshot(data)

      if (data.decompose) {
        const decompose = data.decompose as Record<string, unknown>
        tables.value = {
          condition_table: (decompose.condition_table as MaiteTableRow[]) ?? [{ content: '' }],
          step_table: (decompose.step_table as MaiteTableRow[]) ?? [{ content: '' }],
          model_table: (decompose.model_table as MaiteTableRow[]) ?? [{ content: '' }],
        }
      }

      diagnosisResult.value = (data.diagnosis as Record<string, unknown>) ?? null
      remedyTasks.value = (data.remedy_tasks as unknown as MaiteRemedyTask[]) ?? []
      variantTasks.value = (data.variant_tasks as unknown as MaiteVariantTask[]) ?? []

      eventBus.emit('maite:inquiry_snapshot_loaded', { snapshot: data })
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'load_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_snapshot',
      })
    } finally {
      loading.value = false
    }
  }

  async function startInquirySession(problemText: string): Promise<number | null> {
    loading.value = true
    errorMessage.value = ''
    try {
      // Reuse session already created at OCR upload when available.
      let sessionId = store.activeSessionId
      if (!sessionId) {
        const session = await persistMaitePractice({
          text: problemText,
          mode: 'inquiry',
        })
        sessionId = session?.id ?? null
      }
      if (!sessionId) {
        throw new Error('create_failed')
      }
      store.setCurrentProblemText(problemText)
      eventBus.emit('maite:session_opened', { sessionId, mode: 'inquiry' })
      await loadSnapshot(sessionId)
      notify.success(t('maite.toast.session_created'))
      return sessionId
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'create_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_create',
      })
      return null
    } finally {
      loading.value = false
    }
  }

  async function submitDecomposeTables(): Promise<void> {
    if (!sessionId.value || decomposeReadonly.value) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      await submitDecompose(sessionId.value, tables.value)
      activeStage.value = 'diagnosis'
      eventBus.emit('maite:practice_invalidate', { reason: 'decompose_submitted' })
      await loadSnapshot(sessionId.value)
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'submit_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_decompose',
      })
    } finally {
      loading.value = false
    }
  }

  async function runDiagnoseAuto(): Promise<void> {
    if (!sessionId.value) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      const result = await diagnoseAuto(sessionId.value, {
        student_input: studentThinking.value,
      })
      diagnosisResult.value = result as Record<string, unknown>
      await diagnoseFinalize(sessionId.value)
      activeStage.value = 'remedy'
      await loadSnapshot(sessionId.value)
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'diagnosis_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_diagnosis',
      })
    } finally {
      loading.value = false
    }
  }

  async function runRemedyGenerate(): Promise<void> {
    if (!sessionId.value) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      remedyTasks.value = await generateRemedyTasks(sessionId.value)
      await loadSnapshot(sessionId.value)
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'remedy_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_remedy',
      })
    } finally {
      loading.value = false
    }
  }

  async function runVariantsGenerate(): Promise<void> {
    if (!sessionId.value) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      variantTasks.value = await generateVariantTasks(sessionId.value)
      activeStage.value = 'variant'
      await loadSnapshot(sessionId.value)
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'variant_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_variant',
      })
    } finally {
      loading.value = false
    }
  }

  async function submitVariantAnswer(
    taskId: number,
    studentAnswer: string,
    studentStrategy: string
  ): Promise<void> {
    if (!sessionId.value) {
      return
    }
    const answer = studentAnswer.trim()
    const strategy = studentStrategy.trim()
    if (!answer || !strategy) {
      errorMessage.value = 'variant_answer_required'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_variant_submit',
      })
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      await submitVariantTask(sessionId.value, taskId, {
        student_answer: answer,
        student_strategy: strategy,
      })
      await loadSnapshot(sessionId.value)
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'variant_submit_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_variant_submit',
      })
    } finally {
      loading.value = false
    }
  }

  async function completeInquiry(): Promise<void> {
    if (!sessionId.value) {
      return
    }
    if (!canComplete.value) {
      errorMessage.value = 'variants_incomplete'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_complete',
      })
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      await completeSession(sessionId.value)
      activeStage.value = 'completed'
      eventBus.emit('maite:practice_invalidate', { reason: 'session_completed' })
      await loadSnapshot(sessionId.value)
      notify.success(t('maite.toast.session_completed'))
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'complete_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'inquiry_complete',
      })
    } finally {
      loading.value = false
    }
  }

  function selectStage(stage: MaiteInquiryStage): void {
    const targetIndex = STAGE_ORDER.indexOf(stage)
    const currentIndex = STAGE_ORDER.indexOf(activeStage.value)
    if (targetIndex < 0 || targetIndex > currentIndex) {
      return
    }
    activeStage.value = stage
    if (sessionId.value) {
      eventBus.emit('maite:stage_changed', {
        sessionId: sessionId.value,
        stage,
        readOnlyPhases: readOnlyPhases.value,
      })
    }
  }

  return {
    loading,
    errorMessage,
    snapshot,
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
  }
}
