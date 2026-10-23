/**
 * Panels Store - Pinia store for panel state management
 * Migrated from StateManager.panels
 *
 * Enhanced with State-to-Event bridge for EventBus integration
 *
 * Lifecycle: reset() is called on canvas exit (CanvasPage onUnmounted) to clear
 * diagramBrainstorm suggestions, property nodeData, and mindmate panel state, avoiding
 * memory leaks from canvas-specific data.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores/diagram'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'
import { useUIStore } from '@/stores/ui'
import type {
  AiBrainstormPanelState,
  AiBrainstormSessionSnapshot,
  ConceptMapTab,
  DiagramBrainstormPanelState,
  DiagramBrainstormSessionSnapshot,
  MindmateMessage,
  MindmatePanelState,
  NodeSuggestion,
  PropertyPanelState,
  UploadedFile,
} from '@/types'
import { isManualViewportMode } from '@/utils/conceptMapDesktopViewport'

export const usePanelsStore = defineStore('panels', () => {
  // State
  const mindmate = ref<MindmatePanelState>({
    open: false,
    conversationId: null,
    isStreaming: false,
    messages: [],
    uploadedFiles: [],
  })

  const diagramBrainstorm = ref<DiagramBrainstormPanelState>({
    open: false,
    suggestions: [],
    selected: [],
    mode: null,
    stage: null,
    stage_data: null,
    useConceptListHeader: false,
  })

  const diagramBrainstormSessionsByDiagram = ref<Map<string, DiagramBrainstormSessionSnapshot>>(
    new Map()
  )

  const aiBrainstorm = ref<AiBrainstormPanelState>({
    open: false,
    suggestions: [],
    selected: [],
    mode: null,
    stage: null,
    stage_data: null,
  })

  const aiBrainstormSessionsByDiagram = ref<Map<string, AiBrainstormSessionSnapshot>>(new Map())

  const property = ref<PropertyPanelState>({
    open: false,
    nodeId: null,
    nodeData: null,
  })

  // Getters
  const anyPanelOpen = computed(
    () =>
      mindmate.value.open ||
      diagramBrainstorm.value.open ||
      aiBrainstorm.value.open ||
      property.value.open
  )
  const isAnyPanelOpen = anyPanelOpen // Alias

  const openPanelCount = computed(() => {
    let count = 0
    if (mindmate.value.open) count++
    if (diagramBrainstorm.value.open) count++
    if (aiBrainstorm.value.open) count++
    if (property.value.open) count++
    return count
  })

  // Panel state accessors for components
  const mindmatePanel = computed(() => ({
    isOpen: mindmate.value.open,
    ...mindmate.value,
  }))

  const diagramBrainstormPanel = computed(() => ({
    isOpen: diagramBrainstorm.value.open,
    ...diagramBrainstorm.value,
  }))

  const aiBrainstormPanel = computed(() => ({
    isOpen: aiBrainstorm.value.open,
    ...aiBrainstorm.value,
  }))

  const propertyPanel = computed(() => ({
    isOpen: property.value.open,
    ...property.value,
  }))

  type CoveringPanel = 'mindmate' | 'aiBrainstorm' | 'diagramBrainstorm'

  /**
   * AI brainstorm (waterfall / AI brainstorm) and conversational edit both cover
   * the canvas. Opening one must close the others so they never stack.
   */
  function closeCoveringPeers(keep: CoveringPanel): void {
    if (keep !== 'mindmate') {
      closeMindmate()
    }
    if (keep !== 'aiBrainstorm') {
      closeAiBrainstorm()
    }
    if (keep !== 'diagramBrainstorm') {
      closeDiagramBrainstorm()
    }
  }

  /** Live panel state wins while this canvas session is open; snapshots are for empty restores. */
  function shouldRestoreCoveringSession(
    liveSuggestions: NodeSuggestion[],
    snapshot: { suggestions: NodeSuggestion[] } | undefined
  ): boolean {
    return liveSuggestions.length === 0 && !!snapshot && snapshot.suggestions.length > 0
  }

  // Actions
  function openMindmate(options: Partial<MindmatePanelState> = {}): void {
    const ls = useLearningAssignmentCanvasStore()
    if (!ls.can('conversational_edit')) {
      return
    }
    closeCoveringPeers('mindmate')
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

  function openDiagramBrainstorm(
    options: Partial<DiagramBrainstormPanelState> & {
      diagramKey?: string
      conceptMapNodeId?: string
      conceptMapNodeText?: string
    } = {}
  ): void {
    if (!useLearningAssignmentCanvasStore().can('ai_brainstorm')) {
      return
    }
    closeCoveringPeers('diagramBrainstorm')
    const wasOpen = diagramBrainstorm.value.open
    const { diagramKey, conceptMapNodeId, conceptMapNodeText, ...restOptions } = options
    const snapshot = diagramKey
      ? diagramBrainstormSessionsByDiagram.value.get(diagramKey)
      : undefined
    const hasRestoredSession =
      !conceptMapNodeId &&
      shouldRestoreCoveringSession(diagramBrainstorm.value.suggestions, snapshot)
    if (hasRestoredSession && snapshot) {
      let conceptMapTabs = snapshot.conceptMapTabs ?? undefined
      let mode = snapshot.mode
      if (conceptMapTabs?.length && diagramKey?.startsWith('concept_map')) {
        const diagramStore = useDiagramStore()
        const nodeIds = new Set((diagramStore.data?.nodes ?? []).map((n) => n.id))
        const kept = conceptMapTabs.filter((t) => t.id === 'topic' || nodeIds.has(t.id))
        conceptMapTabs = kept.length > 0 ? kept : undefined
        if (mode && typeof mode === 'string' && !nodeIds.has(mode) && mode !== 'topic') {
          mode = 'topic'
        }
      }
      diagramBrainstorm.value = {
        ...diagramBrainstorm.value,
        suggestions: snapshot.suggestions,
        selected: snapshot.selected,
        mode,
        stage: snapshot.stage ?? null,
        stage_data: snapshot.stage_data ?? null,
        conceptMapTabs,
        open: true,
        useConceptListHeader: restOptions.useConceptListHeader === true,
      }
    } else {
      let conceptMapTabs: ConceptMapTab[] | undefined = restOptions.conceptMapTabs
      let mode = restOptions.mode ?? null
      if (conceptMapNodeId && conceptMapNodeText) {
        const existingTabs = diagramBrainstorm.value.conceptMapTabs ?? []
        const hasTab = existingTabs.some((t) => t.id === conceptMapNodeId)
        if (!hasTab) {
          conceptMapTabs = [...existingTabs, { id: conceptMapNodeId, name: conceptMapNodeText }]
        }
        mode = conceptMapNodeId
      }
      diagramBrainstorm.value = {
        ...diagramBrainstorm.value,
        open: true,
        ...restOptions,
        conceptMapTabs,
        mode: mode ?? restOptions.mode ?? null,
        useConceptListHeader: restOptions.useConceptListHeader === true,
      }
    }
    if (!wasOpen) {
      eventBus.emit('panel:opened', { panel: 'diagramBrainstorm', isOpen: true, options })
      eventBus.emit('state:panel_opened', {
        panel: 'diagramBrainstorm',
        state: diagramBrainstorm.value,
      })
      eventBus.emit('diagramBrainstorm:opened', { diagramKey, hasRestoredSession })
    } else if (conceptMapNodeId && !hasRestoredSession) {
      eventBus.emit('diagramBrainstorm:opened', {
        diagramKey,
        hasRestoredSession,
        wasPanelAlreadyOpen: true,
      })
    }
  }

  function saveDiagramBrainstormSession(diagramKey: string): void {
    const { suggestions, selected, stage, stage_data, conceptMapTabs } = diagramBrainstorm.value
    let mode = diagramBrainstorm.value.mode
    if (suggestions.length > 0 && diagramKey) {
      let tabsToSave = conceptMapTabs ? [...conceptMapTabs] : undefined
      if (diagramKey.startsWith('concept_map')) {
        const diagramStore = useDiagramStore()
        const nodeIds = new Set((diagramStore.data?.nodes ?? []).map((n) => n.id))
        if (tabsToSave?.length) {
          const kept = tabsToSave.filter((t) => t.id === 'topic' || nodeIds.has(t.id))
          tabsToSave = kept.length > 0 ? kept : undefined
        }
        if (mode && typeof mode === 'string' && mode !== 'topic' && !nodeIds.has(mode)) {
          mode = 'topic'
        }
      }
      const map = new Map(diagramBrainstormSessionsByDiagram.value)
      map.set(diagramKey, {
        suggestions: [...suggestions],
        selected: [...selected],
        mode,
        stage: stage ?? null,
        stage_data: stage_data ?? null,
        conceptMapTabs: tabsToSave,
      })
      diagramBrainstormSessionsByDiagram.value = map
    }
  }

  function clearDiagramBrainstormSession(diagramKey?: string): void {
    if (diagramKey) {
      const map = new Map(diagramBrainstormSessionsByDiagram.value)
      map.delete(diagramKey)
      diagramBrainstormSessionsByDiagram.value = map
    } else {
      diagramBrainstormSessionsByDiagram.value = new Map()
    }
  }

  function openAiBrainstorm(
    options: Partial<AiBrainstormPanelState> & { diagramKey?: string } = {}
  ): void {
    if (!useLearningAssignmentCanvasStore().can('ai_brainstorm')) {
      return
    }
    closeCoveringPeers('aiBrainstorm')
    const wasOpen = aiBrainstorm.value.open
    const { diagramKey, ...restOptions } = options
    const snapshot = diagramKey ? aiBrainstormSessionsByDiagram.value.get(diagramKey) : undefined
    const hasRestoredSession = shouldRestoreCoveringSession(
      aiBrainstorm.value.suggestions,
      snapshot
    )
    if (hasRestoredSession && snapshot) {
      aiBrainstorm.value = {
        ...aiBrainstorm.value,
        suggestions: snapshot.suggestions,
        selected: snapshot.selected,
        mode: snapshot.mode,
        stage: snapshot.stage ?? null,
        stage_data: snapshot.stage_data ?? null,
        sourceTabs: snapshot.sourceTabs,
        open: true,
      }
    } else {
      aiBrainstorm.value = {
        ...aiBrainstorm.value,
        open: true,
        ...restOptions,
      }
    }
    if (!wasOpen) {
      eventBus.emit('panel:opened', { panel: 'aiBrainstorm', isOpen: true, options })
      eventBus.emit('state:panel_opened', { panel: 'aiBrainstorm', state: aiBrainstorm.value })
      eventBus.emit('ai_brainstorm:opened', { diagramKey, hasRestoredSession })
    }
  }

  function saveAiBrainstormSession(diagramKey: string): void {
    const { suggestions, selected, mode, stage, stage_data, sourceTabs } = aiBrainstorm.value
    if (suggestions.length > 0 && diagramKey) {
      const map = new Map(aiBrainstormSessionsByDiagram.value)
      map.set(diagramKey, {
        suggestions: [...suggestions],
        selected: [...selected],
        mode,
        stage: stage ?? null,
        stage_data: stage_data ?? null,
        sourceTabs: sourceTabs ? [...sourceTabs] : undefined,
      })
      aiBrainstormSessionsByDiagram.value = map
    }
  }

  function clearAiBrainstormSession(diagramKey?: string): void {
    if (diagramKey) {
      const map = new Map(aiBrainstormSessionsByDiagram.value)
      map.delete(diagramKey)
      aiBrainstormSessionsByDiagram.value = map
    } else {
      aiBrainstormSessionsByDiagram.value = new Map()
    }
  }

  function migrateAiBrainstormSessionToSavedDiagram(newDiagramId: string): void {
    const oldKey = 'ai-brainstorm-mindmap-new'
    const newKey = `ai-brainstorm-mindmap-${newDiagramId}`
    const snapshot = aiBrainstormSessionsByDiagram.value.get(oldKey)
    if (snapshot) {
      const map = new Map(aiBrainstormSessionsByDiagram.value)
      map.set(newKey, snapshot)
      map.delete(oldKey)
      aiBrainstormSessionsByDiagram.value = map
    }
  }

  function closeAiBrainstorm(): void {
    const wasOpen = aiBrainstorm.value.open
    if (wasOpen) {
      eventBus.emit('ai_brainstorm:streaming_stop_requested', {})
    }
    aiBrainstorm.value.open = false
    if (wasOpen) {
      eventBus.emit('panel:closed', { panel: 'aiBrainstorm', isOpen: false })
      eventBus.emit('state:panel_closed', { panel: 'aiBrainstorm' })
      const diagramStore = useDiagramStore()
      const uiStore = useUIStore()
      if (!isManualViewportMode(diagramStore, uiStore)) {
        setTimeout(() => eventBus.emit('view:fit_diagram_requested', {}), 300)
      }
    }
  }

  function updateAiBrainstorm(updates: Partial<AiBrainstormPanelState>): void {
    aiBrainstorm.value = {
      ...aiBrainstorm.value,
      ...updates,
    }
  }

  function setAiBrainstormSuggestions(suggestions: NodeSuggestion[]): void {
    aiBrainstorm.value.suggestions = suggestions
  }

  function appendAiBrainstormSuggestion(suggestion: NodeSuggestion): void {
    aiBrainstorm.value = {
      ...aiBrainstorm.value,
      suggestions: [...aiBrainstorm.value.suggestions, suggestion],
    }
  }

  function removeAiBrainstormSuggestions(suggestionIds: string[]): void {
    if (suggestionIds.length === 0) return
    const remove = new Set(suggestionIds)
    aiBrainstorm.value = {
      ...aiBrainstorm.value,
      suggestions: aiBrainstorm.value.suggestions.filter((s) => !remove.has(s.id)),
      selected: aiBrainstorm.value.selected.filter((id) => !remove.has(id)),
    }
  }

  function toggleAiBrainstormSelection(nodeId: string): void {
    const index = aiBrainstorm.value.selected.indexOf(nodeId)
    if (index > -1) {
      aiBrainstorm.value.selected.splice(index, 1)
    } else {
      aiBrainstorm.value.selected.push(nodeId)
    }
  }

  function clearAiBrainstormState(options?: { clearSessions?: boolean }): void {
    const clearSessions = options?.clearSessions ?? true
    eventBus.emit('ai_brainstorm:streaming_stop_requested', {})
    aiBrainstorm.value = {
      ...aiBrainstorm.value,
      suggestions: [],
      selected: [],
      mode: null,
      stage: null,
      stage_data: null,
      sourceTabs: undefined,
    }
    if (clearSessions) {
      aiBrainstormSessionsByDiagram.value = new Map()
    }
  }

  /**
   * Migrate AI brainstorm session from unsaved key ({type}-new) to saved key ({type}-{id}).
   * Call when a new diagram is saved so reopen finds the session under the correct key.
   */
  function migrateDiagramBrainstormSessionToSavedDiagram(
    diagramType: string,
    newDiagramId: string
  ): void {
    const dt = diagramType === 'mind_map' ? 'mindmap' : diagramType
    const oldKey = `${dt}-new`
    const newKey = `${dt}-${newDiagramId}`
    const snapshot = diagramBrainstormSessionsByDiagram.value.get(oldKey)
    if (snapshot) {
      const map = new Map(diagramBrainstormSessionsByDiagram.value)
      map.set(newKey, snapshot)
      map.delete(oldKey)
      diagramBrainstormSessionsByDiagram.value = map
    }
  }

  function closeDiagramBrainstorm(): void {
    const wasOpen = diagramBrainstorm.value.open
    if (wasOpen) {
      eventBus.emit('diagram_brainstorm:streaming_stop_requested', {})
    }
    diagramBrainstorm.value.open = false
    if (wasOpen) {
      eventBus.emit('panel:closed', { panel: 'diagramBrainstorm', isOpen: false })
      eventBus.emit('state:panel_closed', { panel: 'diagramBrainstorm' })
      // Re-fit after close when canvas regains space (300ms ≈ slide). Desktop concept maps: manual view only.
      const diagramStore = useDiagramStore()
      const uiStore = useUIStore()
      if (!isManualViewportMode(diagramStore, uiStore)) {
        setTimeout(() => eventBus.emit('view:fit_diagram_requested', {}), 300)
      }
    }
  }

  function updateDiagramBrainstorm(updates: Partial<DiagramBrainstormPanelState>): void {
    diagramBrainstorm.value = {
      ...diagramBrainstorm.value,
      ...updates,
    }
  }

  function setDiagramBrainstormSuggestions(suggestions: NodeSuggestion[]): void {
    diagramBrainstorm.value.suggestions = suggestions
  }

  /** Append a suggestion (for parallel streams merging into same list) */
  function appendDiagramBrainstormSuggestion(suggestion: NodeSuggestion): void {
    diagramBrainstorm.value = {
      ...diagramBrainstorm.value,
      suggestions: [...diagramBrainstorm.value.suggestions, suggestion],
    }
  }

  function removeDiagramBrainstormSuggestions(suggestionIds: string[]): void {
    if (suggestionIds.length === 0) return
    const remove = new Set(suggestionIds)
    diagramBrainstorm.value = {
      ...diagramBrainstorm.value,
      suggestions: diagramBrainstorm.value.suggestions.filter((s) => !remove.has(s.id)),
      selected: diagramBrainstorm.value.selected.filter((id) => !remove.has(id)),
    }
  }

  /**
   * Clear AI brainstorm state.
   * - Always clears live panel state (suggestions, selected, mode, stage, stage_data).
   * - clearSessions: when true (default), clears diagram-keyed sessions map.
   *   Use clearSessions: false for diagram:loaded (switching diagrams) to preserve
   *   other diagrams' sessions. Use default for diagram:type_changed (type switch).
   */
  function clearDiagramBrainstormState(options?: { clearSessions?: boolean }): void {
    const clearSessions = options?.clearSessions ?? true
    eventBus.emit('diagram_brainstorm:streaming_stop_requested', {})
    diagramBrainstorm.value = {
      ...diagramBrainstorm.value,
      suggestions: [],
      selected: [],
      mode: null,
      stage: null,
      stage_data: null,
      conceptMapTabs: undefined,
      useConceptListHeader: false,
    }
    if (clearSessions) {
      diagramBrainstormSessionsByDiagram.value = new Map()
    }
  }

  function toggleDiagramBrainstormSelection(nodeId: string, singleSelect?: boolean): void {
    const index = diagramBrainstorm.value.selected.indexOf(nodeId)
    if (index > -1) {
      diagramBrainstorm.value.selected.splice(index, 1)
    } else if (singleSelect) {
      diagramBrainstorm.value.selected = [nodeId]
    } else {
      diagramBrainstorm.value.selected.push(nodeId)
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
    if (mindmate.value.open) {
      closeMindmate()
      return
    }
    openMindmate()
  }

  function toggleDiagramBrainstormPanel(): void {
    if (diagramBrainstorm.value.open) {
      closeDiagramBrainstorm()
      return
    }
    openDiagramBrainstorm()
  }

  function togglePropertyPanel(): void {
    property.value.open = !property.value.open
  }

  // Alias functions for component compatibility
  function closeMindmatePanel(): void {
    closeMindmate()
  }

  function closeDiagramBrainstormPanel(): void {
    closeDiagramBrainstorm()
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
    closeDiagramBrainstorm()
    closeAiBrainstorm()
    closeProperty()
    eventBus.emit('panel:all_closed', {})
  }

  /**
   * Reset all panel state. Called on canvas exit to avoid memory leaks.
   */
  function reset(): void {
    eventBus.emit('diagram_brainstorm:streaming_stop_requested', {})
    eventBus.emit('ai_brainstorm:streaming_stop_requested', {})
    mindmate.value = {
      open: false,
      conversationId: null,
      isStreaming: false,
      messages: [],
      uploadedFiles: [],
    }
    diagramBrainstorm.value = {
      open: false,
      suggestions: [],
      selected: [],
      mode: null,
      stage: null,
      stage_data: null,
      useConceptListHeader: false,
    }
    diagramBrainstormSessionsByDiagram.value = new Map()
    aiBrainstorm.value = {
      open: false,
      suggestions: [],
      selected: [],
      mode: null,
      stage: null,
      stage_data: null,
    }
    aiBrainstormSessionsByDiagram.value = new Map()
    property.value = {
      open: false,
      nodeId: null,
      nodeData: null,
    }
  }

  return {
    // State
    mindmate,
    diagramBrainstorm,
    aiBrainstorm,
    property,

    // Getters
    anyPanelOpen,
    isAnyPanelOpen,
    openPanelCount,
    mindmatePanel,
    diagramBrainstormPanel,
    aiBrainstormPanel,
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
    openDiagramBrainstorm,
    saveDiagramBrainstormSession,
    clearDiagramBrainstormSession,
    migrateDiagramBrainstormSessionToSavedDiagram,
    closeDiagramBrainstorm,
    closeDiagramBrainstormPanel,
    toggleDiagramBrainstormPanel,
    updateDiagramBrainstorm,
    setDiagramBrainstormSuggestions,
    appendDiagramBrainstormSuggestion,
    removeDiagramBrainstormSuggestions,
    clearDiagramBrainstormState,
    toggleDiagramBrainstormSelection,
    openAiBrainstorm,
    closeAiBrainstorm,
    updateAiBrainstorm,
    setAiBrainstormSuggestions,
    appendAiBrainstormSuggestion,
    removeAiBrainstormSuggestions,
    toggleAiBrainstormSelection,
    saveAiBrainstormSession,
    clearAiBrainstormSession,
    migrateAiBrainstormSessionToSavedDiagram,
    clearAiBrainstormState,
    openProperty,
    closeProperty,
    closePropertyPanel,
    togglePropertyPanel,
    updateProperty,
    closeAllPanels,
    reset,
  }
})
