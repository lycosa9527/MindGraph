/**
 * Education-stage (学段) options for AI diagram generation preferences.
 * Values are persisted as Chinese labels on the user row.
 */

export const EDUCATION_STAGES = ['小学', '初中', '高中', '大学', '成人', '专家'] as const

export type EducationStage = (typeof EDUCATION_STAGES)[number]

const EDUCATION_STAGE_SET = new Set<string>(EDUCATION_STAGES)

export function isEducationStage(value: string | null | undefined): value is EducationStage {
  return typeof value === 'string' && EDUCATION_STAGE_SET.has(value)
}

const STAGE_EN_LABEL: Record<EducationStage, string> = {
  小学: 'primary school',
  初中: 'middle school',
  高中: 'high school',
  大学: 'university',
  成人: 'adult learners',
  专家: 'expert / professional',
}

/**
 * Build generation_instructions text for the selected 学段.
 * Returns undefined when unset so auto-complete stays unchanged.
 */
export function buildEducationStageInstructions(
  stage: EducationStage | null | undefined,
  language: string
): string | undefined {
  if (!stage || !isEducationStage(stage)) {
    return undefined
  }
  const isZh = language.toLowerCase().startsWith('zh')
  if (isZh) {
    if (stage === '成人') {
      return '请按成人学习者水平生成图示。内容应专业、实用，用语清晰，适合成人学习与工作场景。'
    }
    if (stage === '专家') {
      return '请按专家/专业人士水平生成图示。内容应深入、严谨，可使用专业术语，适合领域专家阅读。'
    }
    return `请按${stage}学段生成图示。内容深度、用词与示例应符合该学段学习者的认知水平。`
  }
  if (stage === '成人') {
    return 'Generate this diagram for adult learners. Keep content practical and clear for workplace or lifelong-learning contexts.'
  }
  if (stage === '专家') {
    return 'Generate this diagram for expert / professional readers. Use rigorous depth and domain terminology where appropriate.'
  }
  return `Generate this diagram for a ${STAGE_EN_LABEL[stage]} audience. Match depth, wording, and examples to that learner level.`
}

/** Merge 学段 instructions with optional caller-supplied generation text. */
export function mergeGenerationInstructions(
  stageBlock: string | undefined,
  callerInstructions: string | undefined
): string | undefined {
  const stage = (stageBlock ?? '').trim()
  const caller = (callerInstructions ?? '').trim()
  if (stage && caller) {
    return `${stage}\n\n${caller}`
  }
  if (stage) {
    return stage
  }
  if (caller) {
    return caller
  }
  return undefined
}
