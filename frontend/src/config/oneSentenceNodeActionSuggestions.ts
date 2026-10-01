/**
 * Rotating suggestion prompts for the one-sentence (对话式修改) Kitty input.
 * Phrases mirror ``NODE_ACTION_ROWS`` examples in
 * ``services/kitty/routing/node_action_library.py``.
 */

export const ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS = [
  'canvas.mindMapOneSentence.suggestion.add_node',
  'canvas.mindMapOneSentence.suggestion.update_node',
  'canvas.mindMapOneSentence.suggestion.update_center',
  'canvas.mindMapOneSentence.suggestion.delete_node',
  'canvas.mindMapOneSentence.suggestion.auto_complete_branch',
  'canvas.mindMapOneSentence.suggestion.auto_complete',
  'canvas.mindMapOneSentence.suggestion.explain_node',
  'canvas.mindMapOneSentence.suggestion.explain_node.this',
  'canvas.mindMapOneSentence.suggestion.set_content_level',
  'canvas.mindMapOneSentence.suggestion.set_branch_numbering',
] as const

export type OneSentenceNodeActionSuggestionKey =
  (typeof ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS)[number]

const MIND_MAP_ONLY_ONE_SENTENCE_KEYS = new Set<OneSentenceNodeActionSuggestionKey>([
  'canvas.mindMapOneSentence.suggestion.auto_complete_branch',
  'canvas.mindMapOneSentence.suggestion.set_branch_numbering',
])

/** Branch fill and numbering exist on mind maps. Other diagrams keep the shared edits. */
export function oneSentenceSuggestionKeysForDiagram(
  diagramType: string | null | undefined
): readonly OneSentenceNodeActionSuggestionKey[] {
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    return ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS
  }
  return ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS.filter(
    (key) => !MIND_MAP_ONLY_ONE_SENTENCE_KEYS.has(key)
  )
}

/** Match landing-page example rotation cadence. */
export const ONE_SENTENCE_SUGGESTION_ROTATE_MS = 5000
