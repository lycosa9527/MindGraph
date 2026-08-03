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
] as const

export type OneSentenceNodeActionSuggestionKey =
  (typeof ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS)[number]

/** Match landing-page example rotation cadence. */
export const ONE_SENTENCE_SUGGESTION_ROTATE_MS = 5000
