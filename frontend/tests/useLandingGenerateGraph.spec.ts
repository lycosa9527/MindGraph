import { effectScope } from 'vue'

import { describe, expect, it } from 'vitest'

import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type { useNotifications } from '@/composables/core/useNotifications'
import {
  resolveLandingPhaseToastBucket,
  shouldShowLandingPhaseToast,
  useLandingGenerateGraph,
} from '@/composables/mindgraph/useLandingGenerateGraph'
import type { GenerateGraphStreamPhase } from '@/utils/generateGraphStream'

const FULL_SSE_PHASES: GenerateGraphStreamPhase[] = [
  'accepted',
  'detecting',
  'requirements',
  'progress',
  'waiting',
  'streaming',
]

function collectToastBuckets(
  phases: Array<GenerateGraphStreamPhase | 'client_sent'>
): LandingPhaseToastBucket[] {
  const shown = new Set<LandingPhaseToastBucket>()
  const emitted: LandingPhaseToastBucket[] = []
  for (const phase of phases) {
    const bucket = resolveLandingPhaseToastBucket(phase)
    if (!shouldShowLandingPhaseToast(bucket, shown)) {
      continue
    }
    shown.add(bucket)
    emitted.push(bucket)
  }
  return emitted
}

type LandingPhaseToastBucket =
  | 'landing.international.phaseRequestSent'
  | 'landing.international.phaseServerReceived'
  | 'landing.international.phasePleaseWait'
  | 'landing.international.phaseCompleteNavigate'
  | 'generating_detail'
  | 'silent'

describe('resolveLandingPhaseToastBucket', () => {
  it('keeps early phases silent so they do not stack with the progress toast', () => {
    expect(resolveLandingPhaseToastBucket('client_sent')).toBe('silent')
    expect(resolveLandingPhaseToastBucket('accepted')).toBe('silent')
    expect(resolveLandingPhaseToastBucket('detecting')).toBe('silent')
    expect(resolveLandingPhaseToastBucket('requirements')).toBe('silent')
  })

  it('uses generating_detail bucket for progress and waiting', () => {
    expect(resolveLandingPhaseToastBucket('progress')).toBe('generating_detail')
    expect(resolveLandingPhaseToastBucket('waiting')).toBe('generating_detail')
  })

  it('does not toast streaming (ring UI only)', () => {
    expect(resolveLandingPhaseToastBucket('streaming')).toBe('silent')
  })
})

describe('shouldShowLandingPhaseToast', () => {
  it('skips please_wait after generating_detail was shown', () => {
    const shown = new Set<LandingPhaseToastBucket>(['generating_detail'])
    expect(shouldShowLandingPhaseToast('landing.international.phasePleaseWait', shown)).toBe(false)
  })

  it('skips silent buckets', () => {
    expect(shouldShowLandingPhaseToast('silent', new Set())).toBe(false)
  })
})

describe('landing generation toast sequence', () => {
  it('emits one progress toast for a full SSE run', () => {
    const buckets = collectToastBuckets(['client_sent', ...FULL_SSE_PHASES])
    expect(buckets).toEqual(['generating_detail'])
  })

  it('emits one progress toast for legacy accepted/waiting/streaming SSE', () => {
    const buckets = collectToastBuckets(['client_sent', 'accepted', 'waiting', 'streaming'])
    expect(buckets).toEqual(['generating_detail'])
  })
})

function mountLandingGeneration() {
  const scope = effectScope()
  let api: ReturnType<typeof useLandingGenerateGraph> | undefined
  scope.run(() => {
    api = useLandingGenerateGraph({
      t: ((key: string) => key) as UseLanguageTranslate,
      notify: {
        info() {
          return undefined
        },
        error() {
          return undefined
        },
        success() {
          return undefined
        },
        warning() {
          return undefined
        },
      } as unknown as ReturnType<typeof useNotifications>,
    })
  })
  if (!api) {
    scope.stop()
    throw new Error('landing generation scope did not start')
  }
  const generation = api
  return {
    generation,
    stop() {
      scope.stop()
    },
  }
}

describe('landing generation session', () => {
  it('does not cancel another surface when this one closes', () => {
    const landing = mountLandingGeneration()
    const remote = mountLandingGeneration()
    landing.generation.beginGeneration()
    remote.stop()
    expect(landing.generation.isGenerating.value).toBe(true)
    landing.stop()
    expect(landing.generation.isGenerating.value).toBe(false)
  })

  it('ignores a stale finish after a newer run has started', () => {
    const first = mountLandingGeneration()
    const second = mountLandingGeneration()
    const stale = first.generation.beginGeneration()
    const current = second.generation.beginGeneration()
    first.generation.endGeneration(stale)
    expect(second.generation.isCurrentRun(current.runId)).toBe(true)
    expect(second.generation.isGenerating.value).toBe(true)
    second.generation.endGeneration(current)
    expect(second.generation.isGenerating.value).toBe(false)
    expect(second.generation.isCurrentRun(stale.runId)).toBe(false)
    first.stop()
    second.stop()
  })

  it('drops a finished run that has not navigated yet when the user picks another diagram', () => {
    const remote = mountLandingGeneration()
    const run = remote.generation.beginGeneration()
    remote.generation.releaseRun(run)
    expect(remote.generation.isCurrentRun(run.runId)).toBe(true)
    remote.generation.cancelInFlightGeneration()
    expect(remote.generation.isCurrentRun(run.runId)).toBe(false)
    expect(remote.generation.isGenerating.value).toBe(false)
    remote.generation.endGeneration(run)
    expect(remote.generation.isGenerating.value).toBe(false)
    remote.stop()
  })
})
