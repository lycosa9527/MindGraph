/**
 * Pinia Stores Index
 */

export {
  useDiagramStore,
  subscribeToDiagramEvents,
  type DiagramEventType,
  type DiagramEvent,
} from './diagram'
export { usePanelsStore } from './panels'
export { useAuthStore } from './auth'
export { useUIStore, type AppMode, DIAGRAM_TEMPLATES } from './ui'
export { useVoiceStore } from './voice'
export { useMindMateStore, type MindMateConversation } from './mindmate'
export {
  useSavedDiagramsStore,
  type SavedDiagram,
  type SavedDiagramFull,
  type AutoSaveResult,
} from './savedDiagrams'
export { useLLMResultsStore, type LLMResult, type LLMModel, type ModelState } from './llmResults'
export { useAskOnceStore, type AskOnceMessage, type ModelResponse, type ModelId } from './askonce'
export { useKnowledgeSpaceStore, type KnowledgeDocument } from './knowledgeSpace'
export { useFeatureFlagsStore } from './featureFlags'
export { useLibraryStore } from './library'
export { useSmartResponseStore, type Watch, type SmartResponseSession } from './smartResponse'