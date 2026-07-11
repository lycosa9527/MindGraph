/**
 * live_context → Pinia recovery must prefer canonical nodes/connections.
 */
import { describe, expect, it } from 'vitest'

import { canonicalizeLiveContextDiagramData } from '@/composables/kitty/syncDiagramStoreFromVoiceContext'

describe('canonicalizeLiveContextDiagramData', () => {
  it('drops flat children when nodes[] is present so loadFromSpec uses Pinia SoT', () => {
    const raw = {
      topic: '咖啡',
      children: [
        { id: 'branch-r-1-0', text: '产地', index: 0 },
        { id: 'branch-r-1-0-0', text: '巴西', index: 1 },
        { id: 'branch-r-1-4', text: '历史', index: 2 },
      ],
      nodes: [
        { id: 'topic', text: '咖啡' },
        { id: 'branch-r-1-0', text: '产地' },
        { id: 'branch-r-1-0-0', text: '巴西' },
        { id: 'branch-r-1-4', text: '历史' },
      ],
      connections: [
        { source: 'topic', target: 'branch-r-1-0' },
        { source: 'branch-r-1-0', target: 'branch-r-1-0-0' },
        { source: 'topic', target: 'branch-r-1-4' },
      ],
    }

    const out = canonicalizeLiveContextDiagramData(raw)
    expect(out.children).toBeUndefined()
    expect(Array.isArray(out.nodes)).toBe(true)
    expect((out.nodes as unknown[]).length).toBe(4)
    expect(out.connections).toEqual(raw.connections)
  })

  it('keeps children-only payloads for legacy voice-shaped live_spec', () => {
    const raw = {
      topic: '咖啡',
      children: [{ text: '历史' }],
    }
    const out = canonicalizeLiveContextDiagramData(raw)
    expect(out.children).toEqual(raw.children)
    expect(out.nodes).toBeUndefined()
  })
})
