import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  streamShowcaseTeachingCopy,
  teachingCopyFingerprint,
} from '@/composables/showcase/generateShowcaseTeachingCopy'

vi.mock('@/utils/apiClient', () => ({
  apiUpload: vi.fn(),
}))

import { apiUpload } from '@/utils/apiClient'

function sseResponse(lines: string[]): Response {
  const body = lines.map((line) => `${line}\n`).join('')
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

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

describe('streamShowcaseTeachingCopy', () => {
  beforeEach(() => {
    vi.mocked(apiUpload).mockReset()
  })

  it('invokes field callbacks from SSE events and returns done payload', async () => {
    const file = new File(['doc'], 'lesson.pdf', { type: 'application/pdf' })
    vi.mocked(apiUpload).mockResolvedValue(
      sseResponse([
        'data: {"event":"phase","phase":"extracting"}',
        'data: {"event":"phase","phase":"generating"}',
        'data: {"event":"fields","description":"简介半"}',
        'data: {"event":"fields","description":"简介完整","design_highlights":"亮点"}',
        'data: {"event":"done","description":"简介完整","design_highlights":"亮点","teaching_reflection":"反思","model":"qwen3.7-flash"}',
      ]),
    )

    const phases: string[] = []
    const fieldSnaps: Array<Record<string, string | undefined>> = []
    const result = await streamShowcaseTeachingCopy(
      { file, title: '课例', subject: '语文', grade: '六年级' },
      {
        onPhase: (phase) => phases.push(phase),
        onFields: (fields) => fieldSnaps.push({ ...fields }),
      },
    )

    expect(apiUpload).toHaveBeenCalledWith(
      '/api/showcase/ai/teaching-copy/stream',
      expect.any(FormData),
      expect.objectContaining({ signal: undefined }),
    )
    expect(phases).toEqual(['extracting', 'generating'])
    expect(fieldSnaps[0]?.description).toBe('简介半')
    expect(fieldSnaps[1]?.designHighlights).toBe('亮点')
    expect(result).toEqual({
      description: '简介完整',
      designHighlights: '亮点',
      teachingReflection: '反思',
      model: 'qwen3.7-flash',
    })
  })

  it('throws when SSE reports an error event', async () => {
    const file = new File(['doc'], 'lesson.pdf', { type: 'application/pdf' })
    vi.mocked(apiUpload).mockResolvedValue(
      sseResponse(['data: {"event":"error","message":"AI timed out","error_type":"timeout"}']),
    )

    await expect(
      streamShowcaseTeachingCopy({ file, title: '课例', subject: '语文', grade: '六年级' }),
    ).rejects.toThrow('AI timed out')
  })
})
