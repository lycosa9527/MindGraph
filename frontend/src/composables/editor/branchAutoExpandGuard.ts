/**
 * Pure decision logic for File Center auto branch expansion.
 *
 * Kept dependency-free so the guard can be unit-tested without mounting the
 * composable. The composable computes the runtime inputs (placeholder check,
 * graph topology, package readiness) and delegates the yes/no decision here.
 */

export const TOPIC_NODE_ID = 'topic'

export interface BranchAutoExpandState {
  /** Feature flag (knowledge space) is on. */
  enabled: boolean
  /** Current diagram is a mind map. */
  isMindMap: boolean
  /** A live collab session is active (AI expansion disabled). */
  collabActive: boolean
  /** A subgraph generation is already running. */
  isGenerating: boolean
  /** This branch was already auto-expanded (or attempted) this session. */
  alreadyAttempted: boolean
  /** Number of indexed (completed) sources in the linked package. */
  completedSourceCount: number
  /** The committed branch label, trimmed. */
  trimmedText: string
  /** The label is still a placeholder (not a real label). */
  isPlaceholder: boolean
  /** The committed node id. */
  nodeId: string
  /** The node is a direct child of the topic. */
  isTopLevelBranch: boolean
  /** The node already has children. */
  hasChildren: boolean
  /** Diagram is saved and linked (RAG requires diagram_id on the API). */
  diagramSaved: boolean
  /** Live translation is active — skip auto-expand on interim translated labels. */
  liveTranslationActive: boolean
}

/**
 * Decide whether a committed branch label should trigger a package-scoped
 * subgraph suggestion.
 */
export function shouldAutoExpandBranch(state: BranchAutoExpandState): boolean {
  if (!state.enabled || !state.isMindMap) return false
  if (!state.diagramSaved) return false
  if (state.liveTranslationActive) return false
  if (state.collabActive) return false
  if (state.isGenerating) return false
  if (state.alreadyAttempted) return false
  if (state.completedSourceCount < 1) return false
  if (!state.trimmedText || state.isPlaceholder) return false
  if (state.nodeId === TOPIC_NODE_ID) return false
  return state.isTopLevelBranch && !state.hasChildren
}
