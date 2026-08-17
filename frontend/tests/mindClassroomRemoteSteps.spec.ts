import { describe, expect, it } from 'vitest'

import {
  classroomJobFitsLiveNodes,
  collectLiveNodeIds,
  mapRemoteLectureSteps,
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
