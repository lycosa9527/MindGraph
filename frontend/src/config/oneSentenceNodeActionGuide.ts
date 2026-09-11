/**
 * Kitty node-action library rows for the one-sentence panel guide.
 * Mirrors ``NODE_ACTION_ROWS`` edit actions (excludes clarify_options meta).
 */

export const VOICE_NUMBERING_STYLE_IDS = [
  'decimal',
  'chinese',
  'circled',
  'upperAlpha',
  'chineseChapter',
] as const

export type VoiceNumberingStyleId = (typeof VOICE_NUMBERING_STYLE_IDS)[number]

export type OneSentenceNodeActionGuideRow = {
  id: string
  /** Action id for ``kitty.voiceCommand.*`` label. */
  action: string
  /** Example phrase under ``canvas.mindMapOneSentence.suggestion.*``. */
  exampleKey: string
}

export const ONE_SENTENCE_NODE_ACTION_GUIDE_ROWS: OneSentenceNodeActionGuideRow[] = [
  {
    id: 'add_node',
    action: 'add_node',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.add_node',
  },
  {
    id: 'update_node',
    action: 'update_node',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.update_node',
  },
  {
    id: 'update_center',
    action: 'update_center',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.update_center',
  },
  {
    id: 'delete_node',
    action: 'delete_node',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.delete_node',
  },
  {
    id: 'auto_complete_branch',
    action: 'auto_complete_branch',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.auto_complete_branch',
  },
  {
    id: 'auto_complete',
    action: 'auto_complete',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.auto_complete',
  },
  {
    id: 'set_content_level',
    action: 'set_content_level',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.set_content_level',
  },
  {
    id: 'set_branch_numbering',
    action: 'set_branch_numbering',
    exampleKey: 'canvas.mindMapOneSentence.suggestion.set_branch_numbering',
  },
]
