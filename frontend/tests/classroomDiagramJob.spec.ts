import { describe, expect, it } from 'vitest'

import { classroomSlidesToGenerations } from '@/composables/zhihui/classroomDiagramJob'

describe('classroomSlidesToGenerations', () => {
  it('maps classroom slides including partial image urls', () => {
    const rows = classroomSlidesToGenerations({
      id: 'job-1',
      status: 'partial',
      slides: [
        {
          id: 'sl-1',
          slide_index: 0,
          title: 'Open',
          teacher_script: 'Hello class',
          focus_node_ids: ['topic'],
          image_url: '/api/mind-classroom/assets/mind_classroom/generations/a.png',
        },
      ],
    })
    expect(rows).toHaveLength(1)
    expect(rows[0]?.teacher_script).toBe('Hello class')
    expect(rows[0]?.image_url).toContain('/api/mind-classroom/assets/')
  })

  it('reads one-release ZhiHui diagram generations', () => {
    const rows = classroomSlidesToGenerations({
      id: 'legacy-1',
      status: 'complete',
      legacy_zhihui: true,
      generations: [
        {
          id: 'g1',
          slide_title: 'Old deck',
          teacher_script: 'Legacy',
          image_url: '/api/zhihui/assets/zhihui/generations/a.png',
          focus_node_ids: ['topic'],
        },
      ],
    })
    expect(rows[0]?.slide_title).toBe('Old deck')
    expect(rows[0]?.image_url).toContain('/api/zhihui/assets/')
  })
})
