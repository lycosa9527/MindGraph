import { describe, expect, it } from 'vitest'

import {
  loadMindMapSpec,
  nodesAndConnectionsToMindMapSpec,
} from '@/stores/specLoader/mindMap'
import { LEARNING_SHEET_BLANK_TEXT } from '@/stores/specLoader/utils'
import type { Connection, DiagramNode } from '@/types'

function blankedBranch(
  id: string,
  answer: string,
  estimatedWidth: number
): DiagramNode {
  return {
    id,
    text: LEARNING_SHEET_BLANK_TEXT,
    type: 'branch',
    position: { x: 400, y: 200 },
    data: {
      mindMapUid: id,
      mindMapSide: 'right',
      hidden: true,
      hiddenAnswer: answer,
      estimatedWidth,
      estimatedHeight: 40,
    },
  }
}

describe('mind map learning-sheet spec reload', () => {
  it('extracts the answer as branch text so layout keeps underline width', () => {
    const answer = '日内瓦公约与战争法'
    const nodes: DiagramNode[] = [
      {
        id: 'topic',
        text: '军事理论课设计',
        type: 'topic',
        position: { x: 0, y: 0 },
      },
      blankedBranch('branch-a', answer, 220),
      {
        id: 'branch-b',
        text: '核伦理与核稳定',
        type: 'branch',
        position: { x: 0, y: 80 },
        data: { mindMapUid: 'branch-b', mindMapSide: 'left' },
      },
    ]
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'branch-a' },
      { id: 'e2', source: 'topic', target: 'branch-b' },
    ]

    const spec = nodesAndConnectionsToMindMapSpec(nodes, connections)
    const extracted = [...spec.rightBranches, ...spec.leftBranches]
    const blanked = extracted.find((branch) => branch.uid === 'branch-a')
    expect(blanked?.text).toBe(answer)
    expect(blanked?.hidden).toBe(true)
    expect(blanked?.hiddenAnswer).toBe(answer)
  })

  it('re-stamps blanks after loadMindMapSpec', () => {
    const answer = 'photosynthesis and cellular respiration'
    const spec = {
      topic: '军事理论课设计',
      preserveLeftRight: true,
      rightBranches: [
        {
          text: answer,
          uid: 'branch-a',
          hidden: true,
          hiddenAnswer: answer,
        },
      ],
      leftBranches: [
        {
          text: '核伦理与核稳定',
          uid: 'branch-b',
        },
      ],
    }

    const result = loadMindMapSpec(spec, { canvasMode: 'v2' })
    const blanked = result.nodes.find((node) => node.id === 'branch-a')
    expect(blanked?.text).toBe(LEARNING_SHEET_BLANK_TEXT)
    expect((blanked?.data as { hidden?: boolean } | undefined)?.hidden).toBe(true)
    expect((blanked?.data as { hiddenAnswer?: string } | undefined)?.hiddenAnswer).toBe(answer)
  })
})
