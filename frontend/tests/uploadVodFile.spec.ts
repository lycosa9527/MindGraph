import { beforeEach, describe, expect, it, vi } from 'vitest'

import { uploadVodFile } from '@/composables/admin/uploadVodFile'

const signVodUpload = vi.hoisted(() => vi.fn())
const registerVodMedia = vi.hoisted(() => vi.fn())
const sdk = vi.hoisted(() => {
  const constructed: Array<{
    getSignature: () => Promise<string>
    allowReport?: boolean
    enableRaceRegion?: boolean
  }> = []
  const seen: string[] = []

  class TcVod {
    constructor(options: {
      getSignature: () => Promise<string>
      allowReport?: boolean
      enableRaceRegion?: boolean
    }) {
      constructed.push(options)
    }

    upload() {
      return {
        on() {},
        async done() {
          const options = constructed[constructed.length - 1]
          seen.push(await options.getSignature())
          seen.push(await options.getSignature())
          return { fileId: 'file-1' }
        },
      }
    }
  }

  return { constructed, seen, TcVod }
})

vi.mock('@/utils/vodApi', () => ({
  signVodUpload: (...args: unknown[]) => signVodUpload(...args),
  registerVodMedia: (...args: unknown[]) => registerVodMedia(...args),
}))

vi.mock('vod-js-sdk-v6', () => ({
  default: sdk.TcVod,
}))

describe('uploadVodFile', () => {
  beforeEach(() => {
    signVodUpload.mockReset()
    registerVodMedia.mockReset()
    sdk.constructed.length = 0
    sdk.seen.length = 0
  })

  it('mints a fresh one-time signature for each SDK getSignature call', async () => {
    signVodUpload
      .mockResolvedValueOnce({ signature: 'sig-a', source_context: 'ctx-a' })
      .mockResolvedValueOnce({ signature: 'sig-b', source_context: 'ctx-b' })
    registerVodMedia.mockResolvedValue({ id: 'media-1' })

    await uploadVodFile({
      file: new File(['x'], 'clip.mp4', { type: 'video/mp4' }),
      title: 'Clip',
      organizationId: 7,
      folderId: 'folder-1',
    })

    const client = sdk.constructed[0]
    expect(client.allowReport).toBe(false)
    expect(client.enableRaceRegion).toBe(false)
    expect(sdk.seen).toEqual(['sig-a', 'sig-b'])
    expect(signVodUpload).toHaveBeenCalledTimes(2)
    expect(registerVodMedia).toHaveBeenCalledWith({
      fileId: 'file-1',
      title: 'Clip',
      organizationId: 7,
      folderId: 'folder-1',
      sourceContext: 'ctx-b',
    })
  })
})
