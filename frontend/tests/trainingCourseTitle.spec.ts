import { createApp, h } from 'vue'

import { describe, expect, it, vi } from 'vitest'

import TrainingCourseGrid from '@/components/training/TrainingCourseGrid.vue'
import { titleAfterRename } from '@/composables/training/trainingCourseTitle'
import type { TrainingCourse } from '@/types/training'

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
  }),
  useNotifications: () => ({
    successKey: vi.fn(),
    errorKey: vi.fn(),
  }),
}))

function course(partial: Partial<TrainingCourse>): TrainingCourse {
  return {
    id: 'course-1',
    title: 'Visible',
    description: '',
    status: 'draft',
    is_system: false,
    ...partial,
  }
}

describe('titleAfterRename', () => {
  it('updates only the language that matches the visible title', () => {
    expect(
      titleAfterRename(
        course({
          title: '双气泡图教程',
          title_i18n: { zh: '双气泡图教程', en: 'Double Bubble Map tutorial' },
        }),
        '十月更新'
      )
    ).toEqual({ zh: '十月更新', en: 'Double Bubble Map tutorial' })
  })

  it('updates both languages when they share the visible title', () => {
    expect(
      titleAfterRename(
        course({
          title: 'Untitled course',
          title_i18n: { zh: 'Untitled course', en: 'Untitled course' },
        }),
        '校内课'
      )
    ).toEqual({ zh: '校内课', en: '校内课' })
  })

  it('replaces both languages when the visible title matches neither one', () => {
    expect(
      titleAfterRename(course({ title: 'Shown', title_i18n: { zh: '甲', en: 'A' } }), '新课')
    ).toEqual({ zh: '新课', en: '新课' })
  })
})

describe('TrainingCourseGrid', () => {
  it('puts a course menu on the lower right of each thumbnail', () => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const onSelect = vi.fn()
    const app = createApp({
      render() {
        return h(TrainingCourseGrid, {
          courses: [
            course({ id: 'a', title: 'Alpha', is_system: true }),
            course({ id: 'b', title: 'Beta' }),
          ],
          activeCourseId: null,
          onSelect,
        })
      },
    })
    app.mount(host)
    const menus = host.querySelectorAll('.training-course-menu')
    expect(menus).toHaveLength(2)
    for (const menu of menus) {
      const thumb = menu.parentElement
      expect(thumb?.classList.contains('training-course-card__thumb')).toBe(true)
      expect(menu.classList.contains('training-course-card__menu')).toBe(true)
    }
    host.querySelector<HTMLButtonElement>('.training-course-menu__btn')?.click()
    expect(onSelect).not.toHaveBeenCalled()
    host.querySelector<HTMLButtonElement>('.training-course-card__body')?.click()
    expect(onSelect).toHaveBeenCalledTimes(1)
    app.unmount()
    host.remove()
  })
})
