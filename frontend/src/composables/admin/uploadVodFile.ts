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

/** Vite's CJS interop nests `exports.default` one level past the import namespace. */
export function vodSdkConstructor(loaded: unknown): VodJsCtor {
  let current = loaded
  for (let depth = 0; depth < 4; depth += 1) {
    if (typeof current === 'function') {
      return current as VodJsCtor
    }
    if (!current || typeof current !== 'object' || !('default' in current)) {
      break
    }
    const next = (current as { default?: unknown }).default
    if (next === current) {
      break
    }
    current = next
  }
  throw new Error('vod_sdk_ctor_missing')
}

export async function uploadVodFile(options: {
  file: File
  title: string
  organizationId?: number | null
  folderId?: string | null
  onProgress?: (progress: VodUploadProgress) => void
}): Promise<VodMediaItem> {
  // The SDK asks for a signature on ApplyUploadUGC, again on retry, and again
  // on CommitUploadUGC. oneTimeValid signatures cannot be reused. Tencent
  // stores the source context from the apply call, which finishes before
  // byte progress. Later commit signatures must not replace it.
  let sourceContext = ''
  let uploadStarted = false
  const loaded = await import('vod-js-sdk-v6')
  const Ctor = vodSdkConstructor(loaded)
  const client = new Ctor({
    allowReport: false,
    enableRaceRegion: false,
    getSignature: async () => {
      const sign = await signVodUpload(options.organizationId)
      if (!uploadStarted) {
        sourceContext = sign.source_context
      }
      return sign.signature
    },
  })
  const uploader = client.upload({ mediaFile: options.file })
  uploader.on('media_progress', (info) => {
    uploadStarted = true
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
