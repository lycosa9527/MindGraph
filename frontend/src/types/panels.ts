/**
 * Panel Types - Type definitions for UI panels
 */

export interface MindmateMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface UploadedFile {
  id: string
  name: string
  type: string
  size: number
  url?: string
}

export interface MindmatePanelState {
  open: boolean
  conversationId: string | null
  isStreaming: boolean
  messages: MindmateMessage[]
  uploadedFiles: UploadedFile[]
}

export interface NodeSuggestion {
  id: string
  text: string
  type: string
  /** LLM that generated this node (qwen, deepseek, doubao) - used for color coding */
  source_llm?: string
  /** For double bubble: 'similarities' | 'differences' - used to store both in same session */
  mode?: string
  /** For staged stage 2: stable parent id (branch_id, step_id, category_id, part_id) - primary key for tab routing */
  parent_id?: string
  /** For double bubble differences: attribute of left topic */
  left?: string
  /** For double bubble differences: contrasting attribute of right topic */
  right?: string
  /** For double bubble differences: comparison dimension */
  dimension?: string
}

export interface NodePalettePanelState {
  open: boolean
  suggestions: NodeSuggestion[]
  selected: string[]
  /** For double_bubble: 'similarities' | 'differences'. For staged: stage name or parent name */
  mode: string | null
  /** For staged diagrams: 'branches' | 'children', 'steps' | 'substeps', etc. */
  stage?: string | null
  /** For staged stage 2: { branch_name }, { step_name }, { category_name }, { part_name } */
  stage_data?: Record<string, unknown> | null
}

/** Saved session state when user dismisses (X) node palette - restored on reopen */
export interface NodePaletteSessionSnapshot {
  suggestions: NodeSuggestion[]
  selected: string[]
  mode: string | null
  stage?: string | null
  stage_data?: Record<string, unknown> | null
}

export interface PropertyPanelState {
  open: boolean
  nodeId: string | null
  nodeData: Record<string, unknown> | null
}

export interface PanelsState {
  mindmate: MindmatePanelState
  nodePalette: NodePalettePanelState
  property: PropertyPanelState
}
