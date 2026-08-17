import { describe, expect, it } from 'vitest'

import {
  classroomJobLlmModelMatches,
  classroomPrepFitsLiveView,
  classroomPrepSettingsMatch,
  classroomPrepSettingsOf,
  emptyMindClassroomPrep,
  mindClassroomPrepKey,
  parkMindClassroomPrep,
} from '@/utils/mindClassroomPrepSlot'
import type { MindClassroomLectureStep } from '@/utils/mindClassroomScript'

const step: MindClassroomLectureStep = {
  id: 's1',
  kind: 'overview',
  title: 'Open',
  caption: 'Hello',
  bullets: [],
  focusNodeIds: [],
  dwellMs: 1000,
  themeIndex: 0,
}

describe('mindClassroomPrepSlot', () => {
  it('keys prep by saved diagram and selected LLM', () => {
    expect(mindClassroomPrepKey(null, null)).toBe('unsaved:0:default')
    expect(mindClassroomPrepKey(null, 'qwen', 2)).toBe('unsaved:2:qwen')
    expect(mindClassroomPrepKey('diag-1', 'qwen')).toBe('diag-1:qwen')
    expect(mindClassroomPrepKey('diag-1', 'deepseek')).toBe('diag-1:deepseek')
  })

  it('parks a loaded script as ready instead of leaving voice warmup loading', () => {
    const parked = parkMindClassroomPrep({
      jobId: 'job-1',
      jobStatus: 'ready',
      jobProgress: null,
      jobError: null,
      preparedSteps: [step],
      voiceWarmup: 'loading',
      specNodeIds: ['topic'],
      prepSettings: classroomPrepSettingsOf({
        mode: 'canvas_tour',
        mastery: 'first_look',
        tone: 'classroom',
        tourScope: 'main_branch',
        slideStyle: 'general',
        audienceLevel: 'general',
        llmModel: 'qwen',
      }),
    })
    expect(parked.voiceWarmup).toBe('ready')
    expect(parked.preparedSteps).toHaveLength(1)
    expect(emptyMindClassroomPrep().voiceWarmup).toBe('idle')
  })

  it('parks a loading slot with no script as a fresh idle start', () => {
    const parked = parkMindClassroomPrep({
      jobId: null,
      jobStatus: null,
      jobProgress: null,
      jobError: null,
      preparedSteps: [],
      voiceWarmup: 'loading',
      specNodeIds: [],
      prepSettings: null,
    })
    expect(parked.voiceWarmup).toBe('idle')
    expect(parked.preparedSteps).toEqual([])
  })

  it('does not attach another LLM diagram job to the current map', () => {
    expect(classroomJobLlmModelMatches({ llm_model: 'qwen' }, 'qwen')).toBe(true)
    expect(classroomJobLlmModelMatches({ llm_model: 'qwen' }, 'deepseek')).toBe(false)
    expect(classroomJobLlmModelMatches({ llm_model: '' }, 'qwen')).toBe(false)
    expect(classroomJobLlmModelMatches({ llm_model: '' }, null)).toBe(true)
    expect(classroomJobLlmModelMatches({}, null)).toBe(true)
    expect(classroomJobLlmModelMatches(undefined, null)).toBe(false)
  })

  it('keeps a parked script only when the live canvas still has those nodes', () => {
    expect(classroomPrepFitsLiveView(['qwen-a', 'qwen-b'], new Set(['qwen-a']))).toBe(true)
    expect(classroomPrepFitsLiveView(['deepseek-a'], new Set(['qwen-a', 'qwen-b']))).toBe(false)
    expect(classroomPrepFitsLiveView([], new Set(['qwen-a']))).toBe(false)
    expect(
      classroomPrepFitsLiveView(['a', 'b', 'c', 'd'], new Set(['a']))
    ).toBe(false)
  })

  it('does not play a parked script after tone or audience changes', () => {
    const stored = classroomPrepSettingsOf({
      mode: 'canvas_tour',
      mastery: 'first_look',
      tone: 'classroom',
      tourScope: 'main_branch',
      slideStyle: 'general',
      audienceLevel: 'general',
      llmModel: 'qwen',
    })
    expect(classroomPrepSettingsMatch(stored, stored)).toBe(true)
    expect(
      classroomPrepSettingsMatch(stored, { ...stored, tone: 'story' })
    ).toBe(false)
    expect(
      classroomPrepSettingsMatch(stored, { ...stored, audience_level: 'primary' })
    ).toBe(false)
    expect(
      classroomPrepSettingsMatch(stored, { ...stored, language: 'en' })
    ).toBe(false)
    expect(classroomPrepSettingsMatch(null, stored)).toBe(false)
  })
})
