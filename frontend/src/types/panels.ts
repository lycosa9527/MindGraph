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
}

export interface NodePalettePanelState {
  open: boolean
  suggestions: NodeSuggestion[]
  selected: string[]
  mode: string | null
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
