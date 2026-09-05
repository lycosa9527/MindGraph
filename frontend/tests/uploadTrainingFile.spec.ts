import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  filenameForTrainingUpload,
  uploadTrainingFile,
} from '@/composables/training/uploadTrainingFile'

const apiRequest = vi.fn()
const apiUpload = vi.fn()

vi.mock('@/utils/apiClient', () => ({
  apiRequest: (...args: unknown[]) => apiRequest(...args),
  apiUpload: (...args: unknown[]) => apiUpload(...args),
  parseApiErrorDetail: (payload: unknown, fallback: string) => {
    if (payload && typeof payload === 'object' && 'detail' in payload) {
      const detail = (payload as { detail?: unknown }).detail
      if (typeof detail === 'string' && detail.trim()) return detail
    }
    return fallback
  },
}))

const COURSE_ID = '6f2a1c90-db01-4000-8000-00000000db01'

describe('uploadTrainingFile', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    apiUpload.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('adds a suffix when the browser file has no extension', () => {
    const file = new File([new Uint8Array([1])], 'blob', { type: 'image/png' })
    expect(filenameForTrainingUpload(file, 'image/png')).toBe('blob.png')
  })

  it('rejects an empty file before init', async () => {
    await expect(
      uploadTrainingFile(
        COURSE_ID,
        'slide',
        new File([], 'empty.png', { type: 'image/png' })
      )
    ).rejects.toThrow('empty')
    expect(apiRequest).not.toHaveBeenCalled()
  })

  it('PUTs to COS then completes without the file body', async () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'slide.png', {
      type: 'image/png',
    })
    const put = vi.fn(async () => ({ ok: true }))
    vi.stubGlobal('fetch', put)
    apiRequest.mockResolvedValue({
      ok: true,
      json: async () => ({
        key: `courses/${COURSE_ID}/slides/a.png`,
        asset_id: 'asset-1',
        put_url: 'https://cos.example/put',
        backend: 'cos',
        headers: { 'Content-Type': 'image/png' },
      }),
    })
    apiUpload.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'asset-1',
        role: 'slide',
        url: `/api/training/assets/courses/${COURSE_ID}/slides/a.png`,
        logical_key: `courses/${COURSE_ID}/slides/a.png`,
      }),
    })

    const result = await uploadTrainingFile(COURSE_ID, 'slide', file)

    expect(put).toHaveBeenCalledWith(
      'https://cos.example/put',
      expect.objectContaining({ method: 'PUT', body: file })
    )
    const form = apiUpload.mock.calls[0][1] as FormData
    expect(form.get('file')).toBeNull()
    expect(result.id).toBe('asset-1')
  })

  it('completes the upload as multipart instead of JSON', async () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'slide.png', {
      type: 'image/png',
    })
    apiRequest.mockResolvedValue({
      ok: true,
      json: async () => ({
        key: `courses/${COURSE_ID}/slides/a.png`,
        asset_id: 'asset-1',
        put_url: null,
        backend: 'local',
        headers: {},
      }),
    })
    apiUpload.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'asset-1',
        role: 'slide',
        url: `/api/training/assets/courses/${COURSE_ID}/slides/a.png`,
        logical_key: `courses/${COURSE_ID}/slides/a.png`,
      }),
    })

    const result = await uploadTrainingFile(COURSE_ID, 'slide', file)

    expect(apiRequest).toHaveBeenCalledWith(
      '/api/training/assets/init',
      expect.objectContaining({ method: 'POST' })
    )
    expect(apiUpload).toHaveBeenCalledWith(
      '/api/training/assets/complete',
      expect.any(FormData)
    )
    const form = apiUpload.mock.calls[0][1] as FormData
    expect(form.get('course_id')).toBe(COURSE_ID)
    expect(form.get('role')).toBe('slide')
    expect(form.get('file')).toBe(file)
    expect(result.id).toBe('asset-1')
  })

  it('surfaces the server detail when complete fails', async () => {
    apiRequest.mockResolvedValue({
      ok: true,
      json: async () => ({
        key: `courses/${COURSE_ID}/slides/a.png`,
        asset_id: 'asset-1',
        put_url: null,
        backend: 'local',
        headers: {},
      }),
    })
    apiUpload.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'File is too large' }),
    })

    await expect(
      uploadTrainingFile(
        COURSE_ID,
        'slide',
        new File([new Uint8Array([1])], 'slide.png', { type: 'image/png' })
      )
    ).rejects.toThrow('File is too large')
  })
})
