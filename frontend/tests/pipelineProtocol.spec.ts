/**
 * Kitty pipeline protocol: record steps, fail turns, query status.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { emitMock } = vi.hoisted(() => ({
  emitMock: vi.fn(),
}))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    emit: emitMock,
    on: vi.fn(),
    off: vi.fn(),
    onWithOwner: vi.fn(),
    removeAllListenersForOwner: vi.fn(),
  },
}))

vi.mock('@/composables/kitty/kittyAgentDebug', () => ({
  normalizeKittyDebugText: (s: string) => s,
}))

import { createPinia, setActivePinia } from 'pinia'

import {
  beginKittyTurn,
  dumpTurnTrace,
  failKittyTurn,
  getLastFail,
  getTurnStatus,
  recordPipelineEvent,
} from '@/composables/kitty/pipeline'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'

describe('kitty pipeline protocol', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    emitMock.mockClear()
    try {
      window.localStorage.setItem('kitty_workflow_trace', '0')
    } catch {
      /* ignore */
    }
  })

  it('records steps and returns turn status mid-flight', () => {
    const ctx = {
      requestId: 'req-1',
      scope: 'scope-abc',
      lane: 'mobile' as const,
      utteranceId: 'utt-1',
    }
    beginKittyTurn(ctx)
    recordPipelineEvent({
      ctx,
      module: 'history',
      step: 'S06_history_user',
      status: 'started',
    })
    recordPipelineEvent({
      ctx,
      module: 'history',
      step: 'S06_history_user',
      status: 'ok',
    })
    recordPipelineEvent({
      ctx,
      module: 'hub_sync',
      step: 'S07_hub_sync',
      status: 'started',
    })

    const status = getTurnStatus('req-1')
    expect(status.phase).toBe('committing')
    expect(status.module).toBe('hub_sync')
    expect(status.step).toBe('S07_hub_sync')
    expect(status.completedSteps).toContain('S06_history_user')
    expect(emitMock).toHaveBeenCalledWith('kitty:pipeline_step', expect.any(Object))
  })

  it('failKittyTurn sets lastFail with module/step/errorCode and blocks further progress query', () => {
    const ctx = {
      requestId: 'req-fail',
      scope: 'scope-x',
      lane: 'mobile' as const,
    }
    beginKittyTurn(ctx)
    recordPipelineEvent({
      ctx,
      module: 'hub_sync',
      step: 'S07_hub_sync',
      status: 'started',
    })
    failKittyTurn({
      ctx,
      module: 'hub_sync',
      step: 'S07_hub_sync',
      errorCode: 'hub_persist_timeout',
      detail: 'timed out',
    })

    const fail = getLastFail()
    expect(fail).toMatchObject({
      requestId: 'req-fail',
      module: 'hub_sync',
      step: 'S07_hub_sync',
      errorCode: 'hub_persist_timeout',
    })
    const status = getTurnStatus('req-fail')
    expect(status.phase).toBe('failed')
    expect(status.fail?.errorCode).toBe('hub_persist_timeout')
    expect(dumpTurnTrace('req-fail').some((e) => e.status === 'fail')).toBe(true)
    expect(emitMock).toHaveBeenCalledWith(
      'kitty:turn_failed',
      expect.objectContaining({ errorCode: 'hub_persist_timeout' })
    )
    expect(useKittyPipelineStore().editPipelineActive).toBe(false)
  })

  it('ignores other-request events for active-turn phase and lastFail', () => {
    const ctx = {
      requestId: 'req-active',
      scope: 'scope-a',
      lane: 'mobile' as const,
    }
    beginKittyTurn(ctx)
    recordPipelineEvent({
      ctx,
      module: 'hub_sync',
      step: 'S07_hub_sync',
      status: 'ok',
    })

    recordPipelineEvent({
      ctx: {
        requestId: 'lib-other',
        scope: 'scope-a',
        lane: 'mobile',
      },
      module: 'library',
      step: 'S15_library_persist',
      status: 'fail',
      errorCode: 'library_snapshot_failed',
      detail: 'soft',
    })

    const store = useKittyPipelineStore()
    expect(store.pipelinePhase).toBe('committing')
    expect(store.getLastFail()).toBeNull()
    expect(getTurnStatus('req-active').completedSteps).toContain('S07_hub_sync')
    expect(getTurnStatus('req-active').fail).toBeUndefined()
    expect(dumpTurnTrace('lib-other').some((e) => e.status === 'fail')).toBe(true)
  })
})
