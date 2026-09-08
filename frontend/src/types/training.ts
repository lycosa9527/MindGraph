export type TrainingState = 'none' | 'live' | 'paused' | 'ended'

export interface TrainingTopicOption {
  id: string
  label: string
  item_a?: string | null
  item_b?: string | null
  prompt?: string | null
}

export type TrainingSpotlightShape = 'circle' | 'rect'
export type TrainingArrowColor = 'red' | 'amber' | 'green' | 'blue' | 'violet' | 'stone'
export type TrainingArrowLine = 'solid' | 'dashed' | 'thick'
export type TrainingTextAlign = 'left' | 'center' | 'right'

export interface TrainingStepOverlay {
  kind: 'arrow' | 'emoji' | 'text' | 'spotlight' | 'topics' | 'role'
  x?: number
  y?: number
  x2?: number
  y2?: number
  w?: number
  h?: number
  r?: number
  size?: number
  shape?: TrainingSpotlightShape
  color?: TrainingArrowColor
  line?: TrainingArrowLine
  align?: TrainingTextAlign
  bold?: boolean
  italic?: boolean
  ink?: string
  stroke?: string
  step?: number
  glyph?: string
  role?: string
  text?: string
}

export interface TrainingCourseStep {
  id?: string
  position: number
  type: 'canvas' | 'slide' | 'video' | 'page'
  diagram_type?: string | null
  topic_options?: TrainingTopicOption[]
  asset_id?: string | null
  asset_url?: string | null
  thumb_id?: string | null
  thumb_url?: string | null
  overlays?: TrainingStepOverlay[]
  page_key?: string | null
  pull_users?: boolean
  mindmap_canvas_mode?: 'legacy' | 'v2' | null
  modal_key?: string | null
  focus_key?: string | null
  notes?: string | null
  mark_step?: number
  mark_steps?: number
}

export interface TrainingCourse {
  id: string
  title: string
  title_i18n?: { zh?: string; en?: string }
  description: string
  description_i18n?: { zh?: string; en?: string }
  status: 'draft' | 'ready'
  is_system: boolean
  cover_url?: string | null
  first_step?: TrainingCourseStep | null
  steps?: TrainingCourseStep[]
  updated_at?: string | null
}

export interface TrainingSnapshot {
  state: TrainingState
  session_id: string | null
  org_id: number | null
  seq: number
  diagram_type: string | null
  topic_options: TrainingTopicOption[]
  instructor_id: number | null
  instructor_name: string | null
  started_at?: number
  expires_at?: number
  course_id?: string | null
  step_index?: number
  step_count?: number
  step?: TrainingCourseStep | null
  pull_users?: boolean
}

export interface TrainingOrgRow {
  id: number
  name: string
  code: string
}

export interface TrainingReady {
  org_id: number
  teacher_total: number
  online_now: number
}

export interface TrainingRosterRow {
  user_id: number
  name?: string
  page_key?: string | null
  diagram_type?: string | null
  option_id?: string | null
  option_label?: string | null
  generate_state?: string
  updated_at?: number
}

export interface TrainingRosterSummary {
  online: number
  generating: number
  done: number
}
