/**
 * Per-diagram (and per-LLM) launch-prep snapshots for 思维讲堂.
 */
import type { MindClassroomLectureStep } from '@/utils/mindClassroomScript'

export type MindClassroomVoiceWarmup = 'idle' | 'loading' | 'ready' | 'failed'

export type MindClassroomPrepSettings = {
  mode: string
  mastery: string
  tone: string
  tour_scope: string
  slide_style: string
  audience_level: string
  language: 'zh' | 'en'
  llm_model: string
}

export function classroomPrepLanguage(raw: string | null | undefined): 'zh' | 'en' {
  const cleaned = (raw || 'zh').trim().toLowerCase()
  return cleaned.startsWith('zh') ? 'zh' : 'en'
}

export type MindClassroomPrepSnapshot = {
  jobId: string | null
  jobStatus: string | null
  jobProgress: Record<string, unknown> | null
  jobError: string | null
  preparedSteps: MindClassroomLectureStep[]
  voiceWarmup: MindClassroomVoiceWarmup
  specNodeIds: string[]
  prepSettings: MindClassroomPrepSettings | null
}

export function mindClassroomPrepKey(
  diagramId: string | null | undefined,
  llmModel: string | null | undefined,
  unsavedEpoch = 0
): string {
  const model = (llmModel || '').trim() || 'default'
  const diagram = (diagramId || '').trim()
  if (diagram) return `${diagram}:${model}`
  return `unsaved:${unsavedEpoch}:${model}`
}

export function emptyMindClassroomPrep(): MindClassroomPrepSnapshot {
  return {
    jobId: null,
    jobStatus: null,
    jobProgress: null,
    jobError: null,
    preparedSteps: [],
    voiceWarmup: 'idle',
    specNodeIds: [],
    prepSettings: null,
  }
}

export function classroomPrepSettingsOf(input: {
  mode: string
  mastery: string
  tone: string
  tourScope: string
  slideStyle: string
  audienceLevel: string
  language?: string | null
  llmModel: string | null | undefined
}): MindClassroomPrepSettings {
  return {
    mode: input.mode,
    mastery: input.mastery,
    tone: input.tone,
    tour_scope: input.tourScope,
    slide_style: input.slideStyle,
    audience_level: input.audienceLevel,
    language: classroomPrepLanguage(input.language),
    llm_model: (input.llmModel || '').trim(),
  }
}

export function classroomPrepSettingsMatch(
  stored: MindClassroomPrepSettings | null | undefined,
  live: MindClassroomPrepSettings
): boolean {
  if (!stored) return false
  return (
    stored.mode === live.mode &&
    stored.mastery === live.mastery &&
    stored.tone === live.tone &&
    stored.tour_scope === live.tour_scope &&
    stored.slide_style === live.slide_style &&
    stored.audience_level === live.audience_level &&
    stored.language === live.language &&
    stored.llm_model === live.llm_model
  )
}

export function parkMindClassroomPrep(live: MindClassroomPrepSnapshot): MindClassroomPrepSnapshot {
  const hasScript = live.preparedSteps.length > 0
  let warmup = live.voiceWarmup
  if (warmup === 'loading') {
    warmup = hasScript ? 'ready' : 'idle'
  }
  return {
    jobId: live.jobId,
    jobStatus: live.jobStatus,
    jobProgress: live.jobProgress,
    jobError: live.jobError,
    preparedSteps: [...live.preparedSteps],
    voiceWarmup: warmup,
    specNodeIds: [...live.specNodeIds],
    prepSettings: live.prepSettings ? { ...live.prepSettings } : null,
  }
}

export function classroomPrepFitsLiveView(
  specNodeIds: readonly string[] | null | undefined,
  liveIds: Set<string>
): boolean {
  if (!specNodeIds?.length) return false
  const hits = specNodeIds.filter((id) => liveIds.has(id)).length
  return hits * 2 >= specNodeIds.length
}

export function classroomJobLlmModelMatches(
  settings: Record<string, unknown> | undefined,
  selectedModel: string | null | undefined
): boolean {
  if (!settings) return false
  const jobModel = typeof settings.llm_model === 'string' ? settings.llm_model.trim() : ''
  const current = (selectedModel || '').trim()
  if (jobModel) return jobModel === current
  return !current
}
