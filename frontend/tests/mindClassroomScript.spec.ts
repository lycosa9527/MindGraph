import { describe, expect, it } from 'vitest'

import type { Connection, DiagramNode } from '@/types'
import {
  type MindClassroomScriptOptions,
  buildMindClassroomLectureSteps,
  expandLectureFocusNodeIds,
  lectureCaptionDwellMs,
  lectureTtsSafetyMs,
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

  it('keeps the whole main-branch subtree in focus without selecting leaves', () => {
    const steps = buildMindClassroomLectureSteps(nodes, connections, descendants, options())
    const branchStep = steps.find((step) => step.branchNodeId === 'branch-a')
    expect(branchStep?.focusNodeIds).toEqual(['branch-a', 'leaf-a'])
    expect(
      expandLectureFocusNodeIds(
        {
          kind: 'branch',
          focusNodeIds: ['branch-a'],
          branchNodeId: 'branch-a',
        },
        'main_branch',
        descendants
      )
    ).toEqual(['branch-a', 'leaf-a'])
    expect(
      expandLectureFocusNodeIds(
        {
          kind: 'branch',
          focusNodeIds: ['leaf-a'],
          branchNodeId: 'leaf-a',
        },
        'each_node',
        descendants
      )
    ).toEqual(['leaf-a'])
    expect(
      expandLectureFocusNodeIds(
        {
          kind: 'branch',
          focusNodeIds: ['branch-a'],
          branchNodeId: 'branch-a',
        },
        'each_node',
        descendants,
        'slide_deck'
      )
    ).toEqual(['branch-a', 'leaf-a'])
    expect(
      expandLectureFocusNodeIds(
        { kind: 'overview', focusNodeIds: ['topic', 'branch-a'] },
        'main_branch',
        descendants
      )
    ).toEqual(['topic', 'branch-a'])
    expect(
      expandLectureFocusNodeIds(
        { kind: 'branch', focusNodeIds: [], branchNodeId: undefined },
        'main_branch',
        descendants
      )
    ).toEqual([])
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

  it('sizes TTS safety from caption length instead of a 20s cap', () => {
    const caption = '我们先看右上角这一支，地理区位。'.repeat(15)
    const dwell = lectureCaptionDwellMs(caption)
    expect(dwell).toBeGreaterThan(20_000)
    expect(lectureTtsSafetyMs(caption, dwell)).toBeGreaterThan(dwell)
  })

  it('keeps a 4000-char teacher_script under the safety ceiling', () => {
    const caption = '讲'.repeat(4000)
    expect(lectureTtsSafetyMs(caption, 0)).toBeGreaterThan(480_000)
    expect(lectureTtsSafetyMs(caption, 0)).toBeLessThanOrEqual(1_800_000)
  })
})
