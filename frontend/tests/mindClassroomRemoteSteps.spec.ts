import { describe, expect, it } from 'vitest'

import {
  classroomJobFitsLiveNodes,
  classroomReadyJobIsUsable,
  collectLiveNodeIds,
  mapRemoteLectureSteps,
  preparedLectureFitsLive,
  remapPreparedStepsToLive,
} from '@/utils/mindClassroomRemoteSteps'

describe('mapRemoteLectureSteps', () => {
  it('drops focus ids that are not on the live canvas', () => {
    const live = collectLiveNodeIds([{ id: 'topic' }, { id: 'branch' }])
    const steps = mapRemoteLectureSteps(
      [
        {
          id: 's1',
          kind: 'branch',
          title: 'Branch',
          caption: 'Talk',
          focus_node_ids: ['topic', 'missing', 'branch'],
          branch_node_id: 'gone',
          image_url: '/api/mind-classroom/assets/mind_classroom/generations/a.png',
        },
      ],
      live
    )
    expect(steps).toHaveLength(1)
    expect(steps[0]?.focusNodeIds).toEqual(['topic', 'branch'])
    expect(steps[0]?.branchNodeId).toBeUndefined()
    expect(steps[0]?.imageUrl).toContain('mind_classroom/generations')
  })

  it('rejects another LLM map whose node ids are not on the canvas', () => {
    const live = collectLiveNodeIds([{ id: 'qwen-topic' }, { id: 'qwen-b1' }])
    expect(
      classroomJobFitsLiveNodes(
        [
          {
            id: 's1',
            kind: 'branch',
            caption: 'Deepseek talk',
            focus_node_ids: ['deepseek-topic'],
            branch_node_id: 'deepseek-b1',
          },
        ],
        live
      )
    ).toBe(false)
    expect(
      classroomJobFitsLiveNodes(
        [{ id: 's1', kind: 'branch', caption: 'Qwen talk', focus_node_ids: ['qwen-b1'] }],
        live
      )
    ).toBe(true)
    expect(classroomJobFitsLiveNodes([], live)).toBe(true)
  })

  it('treats a Kitty full node-id rewrite as unusable (blue Start)', () => {
    const live = collectLiveNodeIds([{ id: 'new-root' }, { id: 'new-b1' }])
    const steps = [
      {
        id: 'overview-0',
        kind: 'overview' as const,
        title: 'Open',
        caption: 'Welcome',
        bullets: [],
        focusNodeIds: ['old-a', 'old-b'],
        branchNodeId: 'old-a',
        dwellMs: 1000,
        themeIndex: 0,
      },
    ]
    const remapped = remapPreparedStepsToLive(steps, live)
    expect(remapped).toHaveLength(1)
    expect(remapped[0]?.focusNodeIds).toEqual([])
    expect(preparedLectureFitsLive(steps, live, ['old-a', 'old-b'])).toBe(false)
    expect(
      classroomReadyJobIsUsable(
        {
          spec_node_ids: ['old-a', 'old-b'],
          result_json: {
            steps: [{ id: 'overview-0', caption: 'Welcome', focus_node_ids: ['old-a'] }],
          },
        },
        live
      )
    ).toBe(false)
    expect(
      classroomReadyJobIsUsable(
        {
          spec_node_ids: ['old-a'],
          result_json: {
            steps: [{ id: 'overview-0', caption: 'Welcome', focus_node_ids: ['old-a'] }],
            transcript_replaced: true,
          },
        },
        collectLiveNodeIds([{ id: 'old-a' }])
      )
    ).toBe(false)
  })

  it('keeps a ready job when enqueue snapshot ids drifted but the script still hits live nodes', () => {
    const live = collectLiveNodeIds([{ id: 'topic' }, { id: 'branch-1' }])
    expect(
      classroomReadyJobIsUsable(
        {
          spec_node_ids: ['stale-a', 'stale-b', 'stale-c'],
          result_json: {
            steps: [{ id: 'overview-0', caption: 'Welcome', focus_node_ids: ['topic'] }],
          },
        },
        live
      )
    ).toBe(true)
  })

  it('gives long captions enough dwell so TTS is not cut at 20s', () => {
    const live = collectLiveNodeIds([{ id: 'topic' }])
    const caption = '我们先看右上角这一支，地理区位。'.repeat(20)
    const steps = mapRemoteLectureSteps(
      [{ id: 's1', kind: 'branch', title: '区位', caption, focus_node_ids: ['topic'] }],
      live
    )
    expect(steps[0]?.dwellMs).toBeGreaterThan(20_000)
  })
})
