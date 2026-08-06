import { describe, expect, it } from 'vitest'

import {
  getAllEditablePlaceholderLabels,
  isNodeDisplayPlaceholderLabel,
} from '@/stores/diagram/diagramDefaultLabels'

describe('diagram default label display contrast', () => {
  it('does not mute seeded template defaults so nodes keep theme text colors', () => {
    // Circle / double-bubble / bubble / flow template seeds must not use
    // inline-edit-placeholder-display grey (baseline 7c7df0d3 contrast).
    expect(isNodeDisplayPlaceholderLabel('circle_map', 'topic', '主题')).toBe(false)
    expect(isNodeDisplayPlaceholderLabel('circle_map', 'context-0', '联想1')).toBe(false)
    expect(isNodeDisplayPlaceholderLabel('double_bubble_map', 'left-topic', '主题A')).toBe(false)
    expect(isNodeDisplayPlaceholderLabel('double_bubble_map', 'similarity-0', '相似点 1')).toBe(
      false
    )
    expect(isNodeDisplayPlaceholderLabel('bubble_map', 'bubble-0', '属性1')).toBe(false)
    expect(isNodeDisplayPlaceholderLabel('flow_map', 'step-0', '步骤1')).toBe(false)
    expect(isNodeDisplayPlaceholderLabel('mindmap', 'topic', '中心主题')).toBe(false)
  })

  it('still mutes whitespace and editable Enter-text placeholders when locales load', () => {
    expect(isNodeDisplayPlaceholderLabel('circle_map', 'topic', '   ')).toBe(true)
    const editable = getAllEditablePlaceholderLabels()
    expect(editable.length).toBeGreaterThan(0)
    const sample = editable[0]
    expect(isNodeDisplayPlaceholderLabel('circle_map', 'context-0', sample)).toBe(true)
  })
})
