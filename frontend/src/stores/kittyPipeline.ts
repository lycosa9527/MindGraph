/**
 * Kitty pipeline Pinia store — turn phase, step ring buffer, action journal, fail state.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type {
  KittyActionJournalRecord,
  KittyModule,
  KittyPipelineEvent,
  KittyPipelinePhase,
  KittyStep,
  KittyTurnContext,
  KittyTurnFail,
  KittyTurnStatus,
} from '@/composables/kitty/pipeline/types'

const MAX_STEP_EVENTS = 400
const MAX_JOURNAL = 100

export const useKittyPipelineStore = defineStore('kittyPipeline', () => {
  const pipelinePhase = ref<KittyPipelinePhase>('idle')
  const activeTurn = ref<KittyTurnContext | null>(null)
  const lastModule = ref<KittyModule | null>(null)
  const lastStep = ref<KittyStep | null>(null)
  const completedSteps = ref<KittyStep[]>([])
  const stepEvents = ref<KittyPipelineEvent[]>([])
  const lastFail = ref<KittyTurnFail | null>(null)
  const actionJournal = ref<KittyActionJournalRecord[]>([])
  const stepStartedAt = ref<Partial<Record<KittyStep, number>>>({})

  const editPipelineActive = computed(
    () =>
      pipelinePhase.value !== 'idle' &&
      pipelinePhase.value !== 'completed' &&
      pipelinePhase.value !== 'failed'
  )

  function beginTurn(ctx: KittyTurnContext): void {
    activeTurn.value = { ...ctx }
    pipelinePhase.value = 'committing'
    lastModule.value = null
    lastStep.value = null
    completedSteps.value = []
    lastFail.value = null
    stepStartedAt.value = {}
  }

  function setPhase(phase: KittyPipelinePhase): void {
    pipelinePhase.value = phase
  }

  function appendStepEvent(event: KittyPipelineEvent): void {
    stepEvents.value = [...stepEvents.value.slice(-(MAX_STEP_EVENTS - 1)), event]

    const activeId = activeTurn.value?.requestId
    const isActiveTurnEvent =
      activeId != null && event.ctx.requestId === activeId

    // Background / other-request events stay in the ring buffer only so they
    // cannot rewrite mid-turn phase, completedSteps, or lastFail.
    if (!isActiveTurnEvent) {
      return
    }

    lastModule.value = event.module
    lastStep.value = event.step
    if (event.status === 'started') {
      stepStartedAt.value = { ...stepStartedAt.value, [event.step]: event.at }
    }
    if (event.status === 'ok' && !completedSteps.value.includes(event.step)) {
      completedSteps.value = [...completedSteps.value, event.step]
    }
    if (event.status === 'fail') {
      lastFail.value = {
        requestId: event.ctx.requestId,
        module: event.module,
        step: event.step,
        errorCode: event.errorCode ?? 'unknown',
        detail: event.detail,
        at: event.at,
      }
      pipelinePhase.value = 'failed'
    }
  }

  function completeTurn(last?: KittyStep): void {
    if (last && !completedSteps.value.includes(last)) {
      completedSteps.value = [...completedSteps.value, last]
    }
    pipelinePhase.value = 'completed'
  }

  function resetToIdle(): void {
    pipelinePhase.value = 'idle'
    activeTurn.value = null
  }

  function getStepStartedAt(step: KittyStep): number | undefined {
    return stepStartedAt.value[step]
  }

  function getTurnStatus(requestId?: string): KittyTurnStatus {
    const id = requestId?.trim() || activeTurn.value?.requestId
    const events = id
      ? stepEvents.value.filter((e) => e.ctx.requestId === id)
      : stepEvents.value
    const completed = events
      .filter((e) => e.status === 'ok')
      .map((e) => e.step)
      .filter((step, idx, arr) => arr.indexOf(step) === idx)
    const failEvent = [...events].reverse().find((e) => e.status === 'fail')
    const last = events.length > 0 ? events[events.length - 1] : null
    const fail =
      failEvent != null
        ? {
            requestId: failEvent.ctx.requestId,
            module: failEvent.module,
            step: failEvent.step,
            errorCode: failEvent.errorCode ?? 'unknown',
            detail: failEvent.detail,
            at: failEvent.at,
          }
        : lastFail.value != null && lastFail.value.requestId === id
          ? lastFail.value
          : undefined

    let phase = pipelinePhase.value
    if (id && activeTurn.value?.requestId !== id) {
      if (fail) {
        phase = 'failed'
      } else if (completed.includes('S14_history_reply') || completed.includes('S13_mutation_ack')) {
        phase = 'completed'
      }
    }

    return {
      phase,
      module: last?.module ?? lastModule.value,
      step: last?.step ?? lastStep.value,
      completedSteps: completed.length > 0 ? completed : [...completedSteps.value],
      fail,
    }
  }

  function dumpTurnTrace(requestId: string): KittyPipelineEvent[] {
    const id = requestId.trim()
    if (!id) {
      return []
    }
    return stepEvents.value.filter((e) => e.ctx.requestId === id)
  }

  function getLastFail(): KittyTurnFail | null {
    return lastFail.value
  }

  function appendActionJournal(record: KittyActionJournalRecord): void {
    actionJournal.value = [...actionJournal.value.slice(-(MAX_JOURNAL - 1)), record]
  }

  function queryActions(options: {
    requestId?: string
    since?: number
  }): KittyActionJournalRecord[] {
    let rows = actionJournal.value
    if (options.requestId?.trim()) {
      const id = options.requestId.trim()
      rows = rows.filter((r) => r.requestId === id)
    }
    if (typeof options.since === 'number') {
      const since = options.since
      rows = rows.filter((r) => r.at >= since)
    }
    return rows
  }

  function clearTraces(): void {
    stepEvents.value = []
    actionJournal.value = []
    lastFail.value = null
    completedSteps.value = []
    lastModule.value = null
    lastStep.value = null
  }

  return {
    pipelinePhase,
    activeTurn,
    lastModule,
    lastStep,
    completedSteps,
    stepEvents,
    lastFail,
    actionJournal,
    editPipelineActive,
    beginTurn,
    setPhase,
    appendStepEvent,
    completeTurn,
    resetToIdle,
    getStepStartedAt,
    getTurnStatus,
    dumpTurnTrace,
    getLastFail,
    appendActionJournal,
    queryActions,
    clearTraces,
  }
})
