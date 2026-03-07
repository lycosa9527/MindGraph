/**
 * Panels Store - Pinia store for panel state management
 * Migrated from StateManager.panels
 *
 * Enhanced with State-to-Event bridge for EventBus integration
 *
 * Lifecycle: reset() is called on canvas exit (CanvasPage onUnmounted) to clear
 * nodePalette suggestions, property nodeData, and mindmate panel state, avoiding
 * memory leaks from canvas-specific data.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/useEventBus'
import type {
  MindmateMessage,
  MindmatePanelState,
  NodePalettePanelState,
  NodePaletteSessionSnapshot,
  NodeSuggestion,
  PropertyPanelState,
  UploadedFile,
} from '@/types'

export const usePanelsStore = defineStore('panels', () => {
  // State
  const mindmate = ref<MindmatePanelState>({
    open: false,
    conversationId: null,
    isStreaming: false,
    messages: [],
    uploadedFiles: [],
  })

  const nodePalette = ref<NodePalettePanelState>({
    open: false,
    suggestions: [],
    selected: [],
    mode: null,
    stage: null,
    stage_data: null,
  })

  const nodePaletteSessionsByDiagram = ref<Map<string, NodePaletteSessionSnapshot>>(new Map())

  const property = ref<PropertyPanelState>({
    open: false,
    nodeId: null,
    nodeData: null,
  })

  // Getters
  const anyPanelOpen = computed(
    () => mindmate.value.open || nodePalette.value.open || property.value.open
  )
  const isAnyPanelOpen = anyPanelOpen // Alias

  const openPanelCount = computed(() => {
    let count = 0
    if (mindmate.value.open) count++
    if (nodePalette.value.open) count++
    if (property.value.open) count++
    return count
  })

  // Panel state accessors for components
  const mindmatePanel = computed(() => ({
    isOpen: mindmate.value.open,
    ...mindmate.value,
  }))

  const nodePalettePanel = computed(() => ({
    isOpen: nodePalette.value.open,
    ...nodePalette.value,
  }))

  const propertyPanel = computed(() => ({
    isOpen: property.value.open,
    ...property.value,
  }))

  // Actions
  function openMindmate(options: Partial<MindmatePanelState> = {}): void {
    const wasOpen = mindmate.value.open
    mindmate.value = {
      ...mindmate.value,
      open: true,
      ...options,
    }
    if (!wasOpen) {
      eventBus.emit('panel:opened', { panel: 'mindmate', isOpen: true, options })
      eventBus.emit('state:panel_opened', { panel: 'mindmate', state: mindmate.value })
    }
  }

  function closeMindmate(): void {
    const wasOpen = mindmate.value.open
    mindmate.value.open = false
    if (wasOpen) {
      eventBus.emit('panel:closed', { panel: 'mindmate', isOpen: false })
      eventBus.emit('state:panel_closed', { panel: 'mindmate' })
    }
  }

  function updateMindmate(updates: Partial<MindmatePanelState>): void {
    mindmate.value = {
      ...mindmate.value,
      ...updates,
    }
  }

  function addMindmateMessage(message: MindmateMessage): void {
    mindmate.value.messages.push(message)
  }

  function clearMindmateMessages(): void {
    mindmate.value.messages = []
    mindmate.value.conversationId = null
  }

  function setMindmateStreaming(isStreaming: boolean): void {
    mindmate.value.isStreaming = isStreaming
  }

  function addUploadedFile(file: UploadedFile): void {
    mindmate.value.uploadedFiles.push(file)
  }

  function removeUploadedFile(fileId: string): void {
    mindmate.value.uploadedFiles = mindmate.value.uploadedFiles.filter((f) => f.id !== fileId)
  }

  function openNodePalette(options: Partial<NodePalettePanelState> & { diagramKey?: string } = {}): void {
    const wasOpen = nodePalette.value.open
    const { diagramKey, ...restOptions } = options
    const snapshot =
      diagramKey && nodePaletteSessionsByDiagram.value.get(diagramKey)
    const hasRestoredSession = !!(snapshot && snapshot.suggestions.length > 0)
    if (hasRestoredSession) {
      nodePalette.value = {
        ...nodePalette.value,
        suggestions: snapshot.suggestions,
        selected: snapshot.selected,
        mode: snapshot.mode,
        stage: snapshot.stage ?? null,
        stage_data: snapshot.stage_data ?? null,
        open: true,
      }
    } else {
      nodePalette.value = {
        ...nodePalette.value,
        open: true,
        ...restOptions,
      }
    }
    if (!wasOpen) {
      eventBus.emit('panel:opened', { panel: 'nodePalette', isOpen: true, options })
      eventBus.emit('state:panel_opened', { panel: 'nodePalette', state: nodePalette.value })
      eventBus.emit('nodePalette:opened', { diagramKey, hasRestoredSession })
    }
  }

  function saveNodePaletteSession(diagramKey: string): void {
    const { suggestions, selected, mode, stage, stage_data } = nodePalette.value
    if (suggestions.length > 0 && diagramKey) {
      const map = new Map(nodePaletteSessionsByDiagram.value)
      map.set(diagramKey, {
        suggestions: [...suggestions],
        selected: [...selected],
        mode,
        stage: stage ?? null,
        stage_data: stage_data ?? null,
      })
      nodePaletteSessionsByDiagram.value = map
    }
  }

  function clearNodePaletteSession(diagramKey?: string): void {
    if (diagramKey) {
      const map = new Map(nodePaletteSessionsByDiagram.value)
      map.delete(diagramKey)
      nodePaletteSessionsByDiagram.value = map
    } else {
      nodePaletteSessionsByDiagram.value = new Map()
    }
  }

  /**
   * Migrate node palette session from unsaved key ({type}-new) to saved key ({type}-{id}).
   * Call when a new diagram is saved so reopen finds the session under the correct key.
   */
  function migrateNodePaletteSessionToSavedDiagram(
    diagramType: string,
    newDiagramId: string
  ): void {
    const dt = diagramType === 'mind_map' ? 'mindmap' : diagramType
    const oldKey = `${dt}-new`
    const newKey = `${dt}-${newDiagramId}`
    const snapshot = nodePaletteSessionsByDiagram.value.get(oldKey)
    if (snapshot) {
      const map = new Map(nodePaletteSessionsByDiagram.value)
      map.set(newKey, snapshot)
      map.delete(oldKey)
      nodePaletteSessionsByDiagram.value = map
    }
  }

  function closeNodePalette(): void {
    const wasOpen = nodePalette.value.open
    nodePalette.value.open = false
    if (wasOpen) {
      eventBus.emit('panel:closed', { panel: 'nodePalette', isOpen: false })
      eventBus.emit('state:panel_closed', { panel: 'nodePalette' })
      // Re-fit diagram after panel closes (canvas gains space; 300ms matches slide transition)
      setTimeout(() => eventBus.emit('view:fit_diagram_requested', {}), 300)
    }
  }

  function updateNodePalette(updates: Partial<NodePalettePanelState>): void {
    nodePalette.value = {
      ...nodePalette.value,
      ...updates,
    }
  }

  function setNodePaletteSuggestions(suggestions: NodeSuggestion[]): void {
    nodePalette.value.suggestions = suggestions
  }

  /** Append a suggestion (for parallel streams merging into same list) */
  function appendNodePaletteSuggestion(suggestion: NodeSuggestion): void {
    nodePalette.value = {
      ...nodePalette.value,
      suggestions: [...nodePalette.value.suggestions, suggestion],
    }
  }

  /**
   * Clear node palette state.
   * - Always clears live panel state (suggestions, selected, mode, stage, stage_data).
   * - clearSessions: when true (default), clears diagram-keyed sessions map.
   *   Use clearSessions: false for diagram:loaded (switching diagrams) to preserve
   *   other diagrams' sessions. Use default for diagram:type_changed (type switch).
   */
  function clearNodePaletteState(options?: { clearSessions?: boolean }): void {
    const clearSessions = options?.clearSessions ?? true
    nodePalette.value = {
      ...nodePalette.value,
      suggestions: [],
      selected: [],
      mode: null,
      stage: null,
      stage_data: null,
    }
    if (clearSessions) {
      nodePaletteSessionsByDiagram.value = new Map()
    }
  }

  function toggleNodePaletteSelection(
    nodeId: string,
    singleSelect?: boolean
  ): void {
    const index = nodePalette.value.selected.indexOf(nodeId)
    if (index > -1) {
      nodePalette.value.selected.splice(index, 1)
    } else if (singleSelect) {
      nodePalette.value.selected = [nodeId]
    } else {
      nodePalette.value.selected.push(nodeId)
    }
  }

  function openProperty(nodeId: string, nodeData: Record<string, unknown>): void {
    const wasOpen = property.value.open
    property.value = {
      open: true,
      nodeId,
      nodeData,
    }
    if (!wasOpen) {
      eventBus.emit('panel:opened', { panel: 'property', isOpen: true })
      eventBus.emit('state:panel_opened', { panel: 'property', state: property.value })
      eventBus.emit('property_panel:opened', { nodeId })
    }
  }

  function closeProperty(): void {
    const wasOpen = property.value.open
    property.value = {
      open: false,
      nodeId: null,
      nodeData: null,
    }
    if (wasOpen) {
      eventBus.emit('panel:closed', { panel: 'property', isOpen: false })
      eventBus.emit('state:panel_closed', { panel: 'property' })
      eventBus.emit('property_panel:closed', {})
    }
  }

  // Toggle functions for convenience
  function toggleMindmatePanel(): void {
    mindmate.value.open = !mindmate.value.open
  }

  function toggleNodePalettePanel(): void {
    nodePalette.value.open = !nodePalette.value.open
  }

  function togglePropertyPanel(): void {
    property.value.open = !property.value.open
  }

  // Alias functions for component compatibility
  function closeMindmatePanel(): void {
    closeMindmate()
  }

  function closeNodePalettePanel(): void {
    closeNodePalette()
  }

  function closePropertyPanel(): void {
    closeProperty()
  }

  function updateProperty(updates: Partial<PropertyPanelState>): void {
    property.value = {
      ...property.value,
      ...updates,
    }
  }

  function closeAllPanels(): void {
    closeMindmate()
    closeNodePalette()
    closeProperty()
    eventBus.emit('panel:all_closed', {})
  }

  /**
   * Reset all panel state. Called on canvas exit to avoid memory leaks.
   */
  function reset(): void {
    mindmate.value = {
      open: false,
      conversationId: null,
      isStreaming: false,
      messages: [],
      uploadedFiles: [],
    }
    nodePalette.value = {
      open: false,
      suggestions: [],
      selected: [],
      mode: null,
      stage: null,
      stage_data: null,
    }
    nodePaletteSessionsByDiagram.value = new Map()
    property.value = {
      open: false,
      nodeId: null,
      nodeData: null,
    }
  }

  return {
    // State
    mindmate,
    nodePalette,
    property,

    // Getters
    anyPanelOpen,
    isAnyPanelOpen,
    openPanelCount,
    mindmatePanel,
    nodePalettePanel,
    propertyPanel,

    // Actions
    openMindmate,
    closeMindmate,
    closeMindmatePanel,
    toggleMindmatePanel,
    updateMindmate,
    addMindmateMessage,
    clearMindmateMessages,
    setMindmateStreaming,
    addUploadedFile,
    removeUploadedFile,
    openNodePalette,
    saveNodePaletteSession,
    clearNodePaletteSession,
    migrateNodePaletteSessionToSavedDiagram,
    closeNodePalette,
    closeNodePalettePanel,
    toggleNodePalettePanel,
    updateNodePalette,
    setNodePaletteSuggestions,
    appendNodePaletteSuggestion,
    clearNodePaletteState,
    toggleNodePaletteSelection,
    openProperty,
    closeProperty,
    closePropertyPanel,
    togglePropertyPanel,
    updateProperty,
    closeAllPanels,
    reset,
  }
})
