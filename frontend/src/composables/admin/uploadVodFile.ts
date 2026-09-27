/**
 * Client upload to Tencent VOD via vod-js-sdk-v6 + our upload signature.
 */
import { type VodMediaItem, registerVodMedia, signVodUpload } from '@/utils/vodApi'

export interface VodUploadProgress {
  percent: number
}

interface VodJsUploader {
  on: (event: string, handler: (info: { percent?: number }) => void) => void
  done: () => Promise<{ fileId?: string }>
}

interface VodJsClient {
  upload: (options: { mediaFile: File }) => VodJsUploader
}

interface VodJsCtorOptions {
  getSignature: () => Promise<string>
  allowReport?: boolean
  enableRaceRegion?: boolean
}

interface VodJsCtor {
  new (options: VodJsCtorOptions): VodJsClient
}

export async function uploadVodFile(options: {
  file: File
  title: string
  organizationId?: number | null
  folderId?: string | null
  onProgress?: (progress: VodUploadProgress) => void
}): Promise<VodMediaItem> {
  // oneTimeValid signatures are single-use. The SDK calls getSignature for
  // ApplyUploadUGC and again on retry, so each call must mint a new one.
  // Region racing also HEADs hosts outside connect-src, so leave it off.
  let sourceContext = ''
  const module = (await import('vod-js-sdk-v6')) as {
    default?: VodJsCtor
  } & VodJsCtor
  const Ctor = module.default ?? module
  const client = new Ctor({
    allowReport: false,
    enableRaceRegion: false,
    getSignature: async () => {
      const sign = await signVodUpload(options.organizationId)
      sourceContext = sign.source_context
      return sign.signature
    },
  })
  const uploader = client.upload({ mediaFile: options.file })
  uploader.on('media_progress', (info) => {
    const percent = typeof info.percent === 'number' ? info.percent : 0
    options.onProgress?.({ percent })
  })
  const done = await uploader.done()
  const fileId = String(done.fileId || '').trim()
  if (!fileId) {
    throw new Error('vod_upload_no_file_id')
  }
  return registerVodMedia({
    fileId,
    title: options.title,
    organizationId: options.organizationId,
    folderId: options.folderId,
    sourceContext,
  })
}
