/**
 * Maite Learning (迈特学习法) shared frontend types.
 */

export type MaiteMode = 'demo' | 'inquiry' | 'map'

export type MaiteOcrScene = 'demo' | 'question'

export type MaiteStreamStatus = 'idle' | 'streaming' | 'complete' | 'error'

export type MaiteInquiryStage =
  | 'decompose'
  | 'diagnosis'
  | 'remedy'
  | 'variant'
  | 'completed'

export type MaiteTableRow = Record<string, string | number | boolean | null | undefined>

export interface MaiteDecomposeTables {
  condition_table: MaiteTableRow[]
  step_table: MaiteTableRow[]
  model_table: MaiteTableRow[]
  next_question?: string
  opening_guidance?: string
}

export interface MaiteMentorFollowUpResult {
  reply: string
  guiding_question?: string
}

export interface MaiteChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: number
}

export interface MaiteProblem {
  id: number
  user_id: number
  organization_id?: number | null
  source_type: string
  raw_text: string
  clean_text: string
  image_url?: string | null
  subject: string
  grade_level?: string | null
  topic_tags: unknown[]
  difficulty?: string | null
  created_at: string
}

export interface MaiteProblemBankItem {
  id: string | number
  title?: string
  raw_text: string
  subject?: string
  difficulty?: string
}

export interface MaiteOcrResult {
  raw_text: string
  clean_text: string
  stored_path?: string | null
  confidence?: number | null
  extra?: Record<string, unknown>
}

export interface MaiteSession {
  id: number
  user_id: number
  organization_id?: number | null
  problem_id: number
  status: string
  current_stage: MaiteInquiryStage | string
  mode: string
  title?: string | null
  version_no: number
  original_session_id?: number | null
  created_at: string
  updated_at: string
  completed_at?: string | null
}

export interface MaiteSessionSnapshot {
  session: Record<string, unknown>
  problem?: MaiteProblem | Record<string, unknown> | null
  decompose?: Record<string, unknown> | null
  diagnosis?: Record<string, unknown> | null
  remedy_tasks: Record<string, unknown>[]
  variant_tasks: Record<string, unknown>[]
  report?: Record<string, unknown> | null
}

export interface MaitePracticeItem {
  id: number
  title?: string | null
  status: string
  current_stage: string
  problem_text?: string
  updated_at: string
  created_at: string
}

export interface MaiteDiagnosisStageResult {
  stage?: number
  stage_no?: number
  stage_name?: string
  interactions?: unknown[]
  summary?: string
  final_block_report?: Record<string, unknown>[]
  stage_results?: MaiteDiagnosisStageResult[]
}

export interface MaiteRemedyTask {
  id: number
  block_type: string
  block_name: string
  status: string
  task_payload?: Record<string, unknown>
  student_response?: string | null
  ai_feedback?: Record<string, unknown>
}

export interface MaiteVariantTask {
  id: number
  variant_type: string
  variant_text: string
  changed_part?: string
  expected_strategy?: string
  status: string
  student_answer?: string | null
  student_strategy?: string | null
  ai_feedback?: Record<string, unknown>
}

export interface MaiteGraphNode {
  id?: number | string
  node_key: string
  node_name: string
  graph_type: 'knowledge' | 'thinking' | string
  module_id?: string
  status?: string
  mastery_level?: number
}

export interface MaiteGraphResponse {
  student_id: string
  knowledge_nodes: MaiteGraphNode[]
  thinking_nodes: MaiteGraphNode[]
}

export interface MaiteReport {
  report_markdown?: string
  summary?: string
  session_id?: number
}

export interface MaiteMentorStreamCallbacks {
  onStatus?: (status: string) => void
  onPreview?: (text: string) => void
  onComplete?: (payload: unknown) => void
  onError?: (message: string) => void
}

export interface MaiteSelfAssessmentItem {
  name: string
  category: string
  mastered: boolean
  note?: string
  student_added?: boolean
}
