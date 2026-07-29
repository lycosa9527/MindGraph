import { describe, expect, it } from 'vitest'

import { teachingCopyFingerprint } from '@/composables/showcase/generateShowcaseTeachingCopy'

describe('teachingCopyFingerprint', () => {
  it('changes when title or file identity changes', () => {
    const file = new File(['abc'], 'lesson.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const base = teachingCopyFingerprint({
      file,
      title: '两小儿辩日',
      subject: '语文',
      grade: '六年级',
    })
    const retitled = teachingCopyFingerprint({
      file,
      title: '阿Q正传',
      subject: '语文',
      grade: '六年级',
    })
    expect(base).not.toBe(retitled)
    expect(base).toContain('lesson.docx')
  })
})
