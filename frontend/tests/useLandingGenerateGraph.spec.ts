import { describe, expect, it } from 'vitest'

import type { GenerateGraphStreamPhase } from '@/utils/generateGraphStream'
import {
  resolveLandingPhaseToastBucket,
  shouldShowLandingPhaseToast,
} from '@/composables/mindgraph/useLandingGenerateGraph'

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
  it('dedupes identical please-wait toasts across detecting and requirements', () => {
    const pleaseWait = 'landing.international.phasePleaseWait'
    expect(resolveLandingPhaseToastBucket('detecting')).toBe(pleaseWait)
    expect(resolveLandingPhaseToastBucket('requirements')).toBe(pleaseWait)
  })

  it('merges client_sent and accepted into one server-received bucket', () => {
    const serverReceived = 'landing.international.phaseServerReceived'
    expect(resolveLandingPhaseToastBucket('client_sent')).toBe(serverReceived)
    expect(resolveLandingPhaseToastBucket('accepted')).toBe(serverReceived)
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
    expect(
      shouldShowLandingPhaseToast('landing.international.phasePleaseWait', shown)
    ).toBe(false)
  })

  it('skips silent buckets', () => {
    expect(shouldShowLandingPhaseToast('silent', new Set())).toBe(false)
  })
})

describe('landing generation toast sequence', () => {
  it('emits at most three info toasts for a full SSE run', () => {
    const buckets = collectToastBuckets(['client_sent', ...FULL_SSE_PHASES])
    expect(buckets).toEqual([
      'landing.international.phaseServerReceived',
      'landing.international.phasePleaseWait',
      'generating_detail',
    ])
  })

  it('emits two info toasts for legacy accepted/waiting/streaming SSE', () => {
    const buckets = collectToastBuckets(['client_sent', 'accepted', 'waiting', 'streaming'])
    expect(buckets).toEqual([
      'landing.international.phaseServerReceived',
      'generating_detail',
    ])
  })
})
