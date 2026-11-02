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
export type TrainingRoleDepth = 'behind' | 'front'

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
  /** Uploaded mascot WebP. Playback fills src from this id. */
  asset_id?: string | null
  src?: string | null
  depth?: TrainingRoleDepth
  text?: string
  /** Guided-reading node this mark belongs to. Absent marks stay on the slide. */
  node_id?: string
  /** Uploaded picture placed like a mascot, kept distinct from a WebP mascot. */
  link?: 'image'
}

export interface TrainingCourseStep {
  id?: string
  position: number
  type: 'canvas' | 'slide' | 'video' | 'page'
  diagram_type?: string | null
  topic_options?: TrainingTopicOption[]
  asset_id?: string | null
  asset_url?: string | null
  voice_asset_id?: string | null
  voice_url?: string | null
  music_asset_id?: string | null
  music_url?: string | null
  thumb_id?: string | null
  thumb_url?: string | null
  overlays?: TrainingStepOverlay[]
  page_key?: string | null
  pull_users?: boolean
  mandatory?: boolean
  always_play?: boolean
  vod_media_id?: string | null
  vod_autoplay?: boolean
  vod_width?: number | null
  vod_height?: number | null
  mindmap_canvas_mode?: 'legacy' | 'v2' | null
  modal_key?: string | null
  focus_key?: string | null
  ui_lock?: string | null
  notes?: string | null
  mark_step?: number
  mark_steps?: number
  /** Guided reading, drag-to-build, or a node quiz. Absent means off. */
  interact?: TrainingInteract | null
  /** Saved canvas spec for this slide. Reloads the same nodes and edges. */
  diagram_spec?: Record<string, unknown> | null
}

export type TrainingInteractMode = 'read' | 'drag' | 'quiz'

export interface TrainingInteractBlank {
  node_id: string
  answer: string
  /** Shown when a drag-to-build drop on this node is wrong. */
  hint?: string
}

export interface TrainingInteractChoice {
  id: string
  label: string
  correct: boolean
}

export interface TrainingInteractQuiz {
  node_id: string
  prompt: string
  choices: TrainingInteractChoice[]
}

export type TrainingInteractExtraKind = 'note' | 'mascot' | 'video' | 'image'

export interface TrainingInteractNodeExtra {
  node_id: string
  kinds: TrainingInteractExtraKind[]
  /** Library video that plays when the walk reaches this node. */
  vod_media_id?: string | null
}

export interface TrainingInteract {
  mode: TrainingInteractMode
  read_order: string[]
  blanks: TrainingInteractBlank[]
  quizzes: TrainingInteractQuiz[]
  /** Teacher committed the walk order. Playback uses guided reading. */
  sequence_saved: boolean
  /** Live playback position in read_order. Not stored on the course. */
  play_index?: number
  /** Video linked to a walk node. Notes, mascots, and pictures live on overlays. */
  node_extras: TrainingInteractNodeExtra[]
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
  menu_label?: string
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
