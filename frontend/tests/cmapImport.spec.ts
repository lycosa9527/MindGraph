import { describe, expect, it } from 'vitest'

import { looksLikeLinkingPhrase, relationshipsFromOrderedHumanStrings } from '@/utils/cmapImport'
import { normalizeLabel } from '@/utils/cmapLabels'

describe('normalizeLabel', () => {
  it('collapses horizontal whitespace', () => {
    expect(normalizeLabel('  a \t b  \n c')).toBe('a b c')
  })
})

describe('looksLikeLinkingPhrase', () => {
  it('treats numbered lists as concepts', () => {
    expect(looksLikeLinkingPhrase('1. First\n2. Second')).toBe(false)
  })

  it('treats short Latin fragments as links', () => {
    expect(looksLikeLinkingPhrase('may lead to')).toBe(true)
  })

  it('treats colon endings as links', () => {
    expect(looksLikeLinkingPhrase('Requires:')).toBe(true)
  })

  it('uses length threshold for Han script', () => {
    expect(looksLikeLinkingPhrase('连接词')).toBe(true)
    expect(looksLikeLinkingPhrase('这是一个比较长的一般概念标签用于单元测试')).toBe(false)
  })
})

describe('relationshipsFromOrderedHumanStrings', () => {
  it('pairs concepts around linking phrases in stream order', () => {
    const humanOrdered = ['links to', 'Alpha', 'includes', 'Beta', 'Gamma']
    const topic = 'Topic'
    const edges = relationshipsFromOrderedHumanStrings(humanOrdered, topic)
    const labels = edges.map((e) => e.label)
    expect(labels).toContain('links to')
    expect(labels).toContain('includes')
    const includesEdge = edges.find((e) => e.label === 'includes')
    expect(includesEdge?.from).toBe('Beta')
    expect(includesEdge?.to).toBe('Gamma')
  })
})
