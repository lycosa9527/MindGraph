import { describe, expect, it } from 'vitest'

import { isPlaceholderText } from '@/composables/editor/placeholderText'
import { loadLocaleMessages } from '@/i18n'
import {
  getAllEditablePlaceholderLabels,
  isDoubleBubbleDefaultNodeLabel,
  isInsertedBlankNodeLabel,
  isMindmapDefaultNodeLabel,
  isNodeDisplayPlaceholderLabel,
  shouldReplaceLabelWithMathInsert,
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

  it('treats filled double-bubble topics as real, including ones that start with 新', async () => {
    await loadLocaleMessages('zh')
    expect(isDoubleBubbleDefaultNodeLabel('left-topic', '新加坡')).toBe(false)
    expect(isDoubleBubbleDefaultNodeLabel('right-topic', '中国')).toBe(false)
    expect(isDoubleBubbleDefaultNodeLabel('left-topic', 'Topic A')).toBe(true)
    expect(isDoubleBubbleDefaultNodeLabel('left-topic', '主题A')).toBe(true)
    expect(isDoubleBubbleDefaultNodeLabel('right-topic', '主题B')).toBe(true)
    expect(isDoubleBubbleDefaultNodeLabel('left-topic', '')).toBe(true)
  })

  it('treats inserted blank labels as empty and real 新/New topics as filled', async () => {
    await loadLocaleMessages('zh')
    await loadLocaleMessages('de')
    expect(isInsertedBlankNodeLabel('新步骤')).toBe(true)
    expect(isInsertedBlankNodeLabel('新子部分 1')).toBe(true)
    expect(isInsertedBlankNodeLabel('New Step')).toBe(true)
    expect(isInsertedBlankNodeLabel('新加坡')).toBe(false)
    expect(isInsertedBlankNodeLabel('New Zealand')).toBe(false)
    expect(isPlaceholderText('新加坡')).toBe(false)
    expect(isPlaceholderText('中国')).toBe(false)
    expect(isPlaceholderText('New Zealand')).toBe(false)
    expect(isPlaceholderText('新步骤')).toBe(true)
    expect(isPlaceholderText('New Step')).toBe(true)
    expect(isPlaceholderText('Topic A')).toBe(true)
    expect(shouldReplaceLabelWithMathInsert('circle_map', 'topic', '新加坡')).toBe(false)
    expect(shouldReplaceLabelWithMathInsert('circle_map', 'topic', '主题')).toBe(true)
    expect(shouldReplaceLabelWithMathInsert('bubble_map', 'topic', '新加坡')).toBe(false)
    expect(shouldReplaceLabelWithMathInsert('mindmap', 'topic', '新加坡')).toBe(false)
    expect(shouldReplaceLabelWithMathInsert('mindmap', 'topic', 'Zentrumsthema')).toBe(true)
    expect(shouldReplaceLabelWithMathInsert('flow_map', 'flow-topic', '新加坡')).toBe(false)
    expect(shouldReplaceLabelWithMathInsert('tree_map', 'tree-topic', '新加坡')).toBe(false)
    expect(shouldReplaceLabelWithMathInsert('brace_map', 'brace-whole', '新加坡')).toBe(false)
    expect(shouldReplaceLabelWithMathInsert('multi_flow_map', 'event', '新加坡')).toBe(false)
  })

  it('treats default mind-map labels as replaceable on UUID and leftover positional ids', () => {
    expect(isMindmapDefaultNodeLabel('uid-branch', 'Branch 1')).toBe(true)
    expect(isMindmapDefaultNodeLabel('uid-child', 'Child 1.1')).toBe(true)
    expect(isMindmapDefaultNodeLabel('uid-custom', 'Custom')).toBe(false)
    expect(isMindmapDefaultNodeLabel('branch-r-1-0', 'Branch 1')).toBe(true)
    expect(shouldReplaceLabelWithMathInsert('mindmap', 'uid-branch', 'Branch 1')).toBe(true)
    expect(shouldReplaceLabelWithMathInsert('mindmap', 'uid-custom', 'Custom')).toBe(false)
    expect(shouldReplaceLabelWithMathInsert('circle_map', 'uid-context', 'Context 1')).toBe(true)
    expect(shouldReplaceLabelWithMathInsert('circle_map', 'context-0', 'Context 1')).toBe(true)
    expect(shouldReplaceLabelWithMathInsert('circle_map', 'uid-context', 'Custom')).toBe(false)
  })
})
