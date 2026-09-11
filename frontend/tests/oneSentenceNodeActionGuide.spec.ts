/** Guide rows include 专业内容 × 7 dropdown levels and numbering on/off. */
import { describe, expect, it } from 'vitest'

import { AI_CONTENT_LEVEL_IDS } from '@/config/aiContentLevels'
import {
  ONE_SENTENCE_NODE_ACTION_GUIDE_ROWS,
  VOICE_NUMBERING_STYLE_IDS,
} from '@/config/oneSentenceNodeActionGuide'
import { ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS } from '@/config/oneSentenceNodeActionSuggestions'

describe('one-sentence node action guide', () => {
  it('lists content level and numbering next to the structural actions', () => {
    const ids = ONE_SENTENCE_NODE_ACTION_GUIDE_ROWS.map((row) => row.id)
    expect(ids).toContain('set_content_level')
    expect(ids).toContain('set_branch_numbering')
    expect(AI_CONTENT_LEVEL_IDS).toHaveLength(7)
    expect(VOICE_NUMBERING_STYLE_IDS).toEqual([
      'decimal',
      'chinese',
      'circled',
      'upperAlpha',
      'chineseChapter',
    ])
    expect(ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS).toContain(
      'canvas.mindMapOneSentence.suggestion.update_node'
    )
  })

  it('rotates the new phrases in the empty-input suggestions', () => {
    expect(ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS).toContain(
      'canvas.mindMapOneSentence.suggestion.set_content_level'
    )
    expect(ONE_SENTENCE_NODE_ACTION_SUGGESTION_KEYS).toContain(
      'canvas.mindMapOneSentence.suggestion.set_branch_numbering'
    )
  })
})
