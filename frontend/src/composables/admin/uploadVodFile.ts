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

interface VodJsCtor {
  new (options: { getSignature: () => Promise<string> }): VodJsClient
}

export async function uploadVodFile(options: {
  file: File
  title: string
  organizationId?: number | null
  onProgress?: (progress: VodUploadProgress) => void
}): Promise<VodMediaItem> {
  const sign = await signVodUpload(options.organizationId)
  const module = (await import('vod-js-sdk-v6')) as { default?: VodJsCtor } & VodJsCtor
  const Ctor = module.default ?? module
  const client = new Ctor({
    getSignature: async () => sign.signature,
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
    sourceContext: sign.source_context,
  })
}
