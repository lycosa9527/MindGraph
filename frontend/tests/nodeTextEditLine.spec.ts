import { describe, expect, it } from 'vitest'

import { nodeTextEditLine } from '@/diagramBilingual/nodeTextEditLine'

describe('nodeTextEditLine', () => {
  it('keeps a plain double-click on the main line', () => {
    expect(nodeTextEditLine({}, true)).toBe('primary')
    expect(nodeTextEditLine({ ctrlKey: false, metaKey: false }, true)).toBe('primary')
  })

  it('opens the second line when Ctrl or Command is held on a bilingual node', () => {
    expect(nodeTextEditLine({ ctrlKey: true }, true)).toBe('secondary')
    expect(nodeTextEditLine({ metaKey: true }, true)).toBe('secondary')
  })

  it('ignores the modifier when the diagram has no second language', () => {
    expect(nodeTextEditLine({ ctrlKey: true }, false)).toBe('primary')
    expect(nodeTextEditLine({ metaKey: true }, false)).toBe('primary')
  })
})
