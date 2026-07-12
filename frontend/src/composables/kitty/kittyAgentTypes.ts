import type { DiagramType } from '@/types'

export interface KittyAgentOptions {
  ownerId?: string
  sampleRate?: number
  kittyClientLane?: 'mobile'
  /** Text-only panel: no mic, playback, or Omni realtime session. */
  textOnly?: boolean
  onTranscription?: (text: string) => void
  onTextChunk?: (text: string) => void
  onError?: (error: string) => void
  /** Pinia → WS context builder for verified diagram hub persist. */
  buildContext?: () => KittyAgentContext
}

export interface KittyAgentContext {
  diagram_type: DiagramType | string
  active_panel: string
  selected_nodes: string[]
  diagram_data: Record<string, unknown>
  diagram_library_id?: string | null
  diagram_display_title?: string
  interaction_language?: 'zh' | 'en'
  one_sentence_phase?: 'create' | 'edit'
  diagram_write_lock?: { holder: 'llm' | 'tool' | null }
  /** Active multi-LLM pill: qwen | deepseek | doubao (null clears). */
  selected_llm_model?: string | null
}

export interface KittyLibrarySnapshot {
  spec: Record<string, unknown>
  title?: string
  language?: string
  thumbnail?: string | null
}

export interface KittyContextUpdateOptions {
  persistLibrary?: boolean
  librarySnapshot?: KittyLibrarySnapshot
  idempotencyKey?: string
  expectedRevision?: number | null
}

export type KittyAgentState = 'idle' | 'connecting' | 'active' | 'listening' | 'speaking' | 'error'

export interface KittyAudioChunk {
  buffer: AudioBuffer
}
