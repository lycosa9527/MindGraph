import { reactive } from 'vue'

import { describe, expect, it } from 'vitest'

import { cloneDiagramSpecJson } from '@/utils/cloneDiagramSpecJson'

describe('cloneDiagramSpecJson', () => {
  it('clones a Vue reactive spec without sharing identity', () => {
    const spec = reactive({
      type: 'mindmap',
      nodes: [{ id: 'n1', text: '光' }],
    })
    const cloned = cloneDiagramSpecJson(spec)
    expect(cloned).toEqual({
      type: 'mindmap',
      nodes: [{ id: 'n1', text: '光' }],
    })
    expect(cloned).not.toBe(spec)
    expect(cloned.nodes).not.toBe(spec.nodes)
    cloned.nodes = [{ id: 'n1', text: 'Light' }]
    expect(spec.nodes[0].text).toBe('光')
  })
})
