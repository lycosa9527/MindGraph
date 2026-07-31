/**
 * Maite inquiry flow — stage rail, snapshot, diagnosis, remedy, variants, complete.
 */
import { computed, ref } from 'vue'

import { createProblem } from '@/api/maite/problems'
import {
  completeSession,
  createSession,
  getSnapshot,
  submitDecompose,
} from '@/api/maite/inquiry'
import { diagnoseAuto, diagnoseFinalize } from '@/api/maite/diagnosis'
import { generateRemedyTasks } from '@/api/maite/remedy'
import { generateVariantTasks, submitVariantTask } from '@/api/maite/variants'
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

  const sessionId = computed(() => store.activeSessionId)

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
      const problem = await createProblem({ raw_text: problemText.trim() })
      const session = await createSession({
        problem_id: problem.id,
        mode: 'inquiry',
        title: problemText.slice(0, 40),
      })
      store.setActiveSessionId(session.id)
      store.setCurrentProblemText(problemText)
      eventBus.emit('maite:session_opened', { sessionId: session.id, mode: 'inquiry' })
      eventBus.emit('maite:practice_invalidate', { reason: 'session_created' })
      await loadSnapshot(session.id)
      return session.id
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
    if (!sessionId.value) {
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
      activeStage.value = 'variant'
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

  async function submitAllVariantsPlaceholder(): Promise<void> {
    if (!sessionId.value || variantTasks.value.length === 0) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      for (const task of variantTasks.value) {
        if (task.status === 'submitted') {
          continue
        }
        await submitVariantTask(sessionId.value, task.id, {
          student_answer: '占位答案',
          student_strategy: '占位策略',
        })
      }
      await loadSnapshot(sessionId.value)
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'variant_submit_failed'
    } finally {
      loading.value = false
    }
  }

  async function completeInquiry(): Promise<void> {
    if (!sessionId.value) {
      return
    }
    loading.value = true
    errorMessage.value = ''
    try {
      if (variantTasks.value.length === 0) {
        await runVariantsGenerate()
      }
      if (variantTasks.value.some((task) => task.status !== 'submitted')) {
        await submitAllVariantsPlaceholder()
      }
      await completeSession(sessionId.value)
      activeStage.value = 'completed'
      eventBus.emit('maite:practice_invalidate', { reason: 'session_completed' })
      await loadSnapshot(sessionId.value)
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
    sessionId,
    loadSnapshot,
    startInquirySession,
    submitDecomposeTables,
    runDiagnoseAuto,
    runRemedyGenerate,
    runVariantsGenerate,
    completeInquiry,
    selectStage,
  }
}
