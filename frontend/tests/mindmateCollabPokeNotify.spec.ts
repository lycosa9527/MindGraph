import { describe, expect, it, vi } from 'vitest'

import { handleMindmateCollabPokeFrame } from '@/utils/mindmateCollabPokeNotify'

describe('handleMindmateCollabPokeFrame', () => {
  it('shows toast for mindmate_collab_poke frames', () => {
    const notify = { info: vi.fn() }
    const t = (key: string, params?: Record<string, string | number>) => {
      if (key === 'mindmate.collabPokeToast' && params) {
        return `${params.name} -> ${params.seminar}`
      }
      return key
    }
    const handled = handleMindmateCollabPokeFrame(
      {
        type: 'mindmate_collab_poke',
        from_name: '张老师',
        room_title: '教学设计讨论',
      },
      t,
      notify as never,
    )
    expect(handled).toBe(true)
    expect(notify.info).toHaveBeenCalledWith('张老师 -> 教学设计讨论', 7000)
  })

  it('ignores other frame types', () => {
    const notify = { info: vi.fn() }
    const handled = handleMindmateCollabPokeFrame({ type: 'presence' }, (k) => k, notify as never)
    expect(handled).toBe(false)
    expect(notify.info).not.toHaveBeenCalled()
  })
})
