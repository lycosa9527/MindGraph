import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  buildWorkshopDiagramMarkdown,
  embedWorkshopLibraryDiagram,
} from '@/utils/workshopDiagramEmbed'

const apiPost = vi.fn()

vi.mock('@/utils/apiClient', () => ({
  apiPost: (...args: unknown[]) => apiPost(...args),
}))

describe('workshopDiagramEmbed', () => {
  beforeEach(() => {
    apiPost.mockReset()
  })

  it('asks the server to store the PNG and inserts markdown only', async () => {
    apiPost.mockResolvedValue({
      ok: true,
      json: async () => ({
        file_path: '/api/chat/attachments/9/download',
        filename: '背影.png',
      }),
    })

    const id = 'd1d7a7fc-eaa1-436d-abd2-2a7b1230c537'
    const markdown = await embedWorkshopLibraryDiagram({ id, title: '背影' })

    expect(apiPost).toHaveBeenCalledWith(`/api/chat/library-diagrams/${id}`)
    expect(markdown).toBe(
      `![mg:${id}](/api/chat/attachments/9/download)\n<!-- mg-diagram-id:${id} -->`
    )
  })

  it('returns null when the server cannot embed', async () => {
    apiPost.mockResolvedValue({ ok: false })
    const markdown = await embedWorkshopLibraryDiagram({
      id: 'd1d7a7fc-eaa1-436d-abd2-2a7b1230c537',
      title: '背影',
    })
    expect(markdown).toBeNull()
  })
})

describe('buildWorkshopDiagramMarkdown', () => {
  it('embeds a library uuid in alt text and a comment', () => {
    const id = '550e8400-e29b-41d4-a716-446655440000'
    const md = buildWorkshopDiagramMarkdown(id, '背影', '/api/chat/attachments/9/download')
    expect(md).toBe(`![mg:${id}](/api/chat/attachments/9/download)\n<!-- mg-diagram-id:${id} -->`)
  })
})
