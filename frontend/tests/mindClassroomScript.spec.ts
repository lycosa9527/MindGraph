import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import {
  type MindClassroomScriptOptions,
  buildMindClassroomLectureSteps,
} from '@/utils/mindClassroomScript'

const nodes: DiagramNode[] = [
  { id: 'topic', text: 'Topic', type: 'topic', position: { x: 0, y: 0 } },
  { id: 'branch-a', text: 'Branch A', type: 'branch', position: { x: 200, y: 0 } },
  { id: 'leaf-a', text: 'Leaf A', type: 'branch', position: { x: 400, y: 0 } },
  { id: 'branch-b', text: 'Branch B', type: 'branch', position: { x: -200, y: 0 } },
]

const connections: Connection[] = [
  { id: 'edge-a', source: 'topic', target: 'branch-a' },
  { id: 'edge-a-leaf', source: 'branch-a', target: 'leaf-a' },
  { id: 'edge-b', source: 'topic', target: 'branch-b' },
]

function descendants(rootId: string): Set<string> {
  const result = new Set([rootId])
  let changed = true
  while (changed) {
    changed = false
    for (const connection of connections) {
      if (result.has(connection.source) && !result.has(connection.target)) {
        result.add(connection.target)
        changed = true
      }
    }
  }
  return result
}

function options(overrides: Partial<MindClassroomScriptOptions> = {}): MindClassroomScriptOptions {
  return {
    mastery: 'first_look',
    presentation: 'canvas_tour',
    tourScope: 'main_branch',
    tone: 'classroom',
    audienceLevel: 'general',
    audienceTitle: 'General',
    t: (key, params) => `${key}:${JSON.stringify(params ?? {})}`,
    ...overrides,
  }
}

describe('buildMindClassroomLectureSteps', () => {
  it('returns no steps for an empty diagram', () => {
    expect(buildMindClassroomLectureSteps([], [], () => new Set(), options())).toEqual([])
  })

  it('builds an overview, first-level branches, and a closing step', () => {
    const steps = buildMindClassroomLectureSteps(nodes, connections, descendants, options())

    expect(steps.map((step) => step.id)).toEqual([
      'overview-overview',
      'branch-branch-a',
      'branch-branch-b',
      'closing',
    ])
    expect(steps[0]?.bullets).toEqual(['Branch A', 'Branch B'])
    expect(steps.at(-1)?.kind).toBe('closing')
    expect(steps.every((step) => step.dwellMs >= 2_200)).toBe(true)
  })

  it('uses deep traversal and single-node focus for each-node tours', () => {
    const steps = buildMindClassroomLectureSteps(
      nodes,
      connections,
      descendants,
      options({ tourScope: 'each_node' })
    )

    expect(steps.map((step) => step.branchNodeId)).toContain('leaf-a')
    const leafStep = steps.find((step) => step.branchNodeId === 'leaf-a')
    expect(leafStep?.focusNodeIds).toEqual(['leaf-a'])
  })

  it('keeps slide decks on first-level branches unless each-node scope is selected', () => {
    const steps = buildMindClassroomLectureSteps(
      nodes,
      connections,
      descendants,
      options({ presentation: 'slide_deck', tourScope: 'each_node' })
    )

    expect(steps.map((step) => step.branchNodeId)).not.toContain('leaf-a')
  })
})
