import type { DiagramType } from '@/types'

export interface KittyAgentOptions {
  ownerId?: string
  sampleRate?: number
  kittyClientLane?: 'mobile'
  onTranscription?: (text: string) => void
  onTextChunk?: (text: string) => void
  onError?: (error: string) => void
}

export interface KittyAgentContext {
  diagram_type: DiagramType | string
  active_panel: string
  selected_nodes: string[]
  diagram_data: Record<string, unknown>
  diagram_library_id?: string | null
  diagram_display_title?: string
  interaction_language?: 'zh' | 'en'
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
