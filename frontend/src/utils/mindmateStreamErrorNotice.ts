/**
 * Pick a specific MindMate failure notice. Known server text is left unchanged.
 */

export type MindmateNoticeKey =
  | 'mindmate.mainServerDownRetry'
  | 'mindmate.backupServerFailed'
  | 'mindmate.networkRetry'
  | 'mindmate.replyCutOff'
  | 'mindmate.serviceRetry'
  | 'mindmate.noReply'

const PASSTHROUGH_ERROR_TYPES = new Set(['thinking_coin_insufficient', 'daily_token_cap'])

const BROWSER_NETWORK = new Set([
  'failed to fetch',
  'load failed',
  'network error',
  'networkerror when attempting to fetch resource.',
])

export interface MindmateStreamNoticeOptions {
  onBackup: boolean
  hasPartial: boolean
  emptyStream: boolean
  httpStatus?: number
}

function statusFromText(raw: string): number | undefined {
  const match = /^HTTP error! status: (\d+)/i.exec(raw.trim())
  if (!match) {
    return undefined
  }
  return Number(match[1])
}

function isOurServerError(raw: string): boolean {
  const text = raw.trim().toLowerCase()
  return (
    text === 'internal server error' ||
    text === 'an error occurred' ||
    text === 'unknown error' ||
    text === 'no response body' ||
    raw.trim() === '服务器内部错误'
  )
}

function isUpstreamPhrase(raw: string): boolean {
  const text = raw.trim().toLowerCase()
  return text.includes('暂时不可用') || text.includes('temporarily unavailable')
}

function outageKey(onBackup: boolean): MindmateNoticeKey {
  return onBackup ? 'mindmate.backupServerFailed' : 'mindmate.mainServerDownRetry'
}

export function mindmateStreamNoticeKey(
  raw: string | undefined,
  errorType: string | undefined,
  options: MindmateStreamNoticeOptions
): MindmateNoticeKey | null {
  if (errorType && PASSTHROUGH_ERROR_TYPES.has(errorType)) {
    return null
  }
  if (errorType === 'dify_backup_unavailable') {
    return 'mindmate.backupServerFailed'
  }
  if (errorType === 'dify_main_unavailable') {
    return 'mindmate.mainServerDownRetry'
  }
  if (options.emptyStream) {
    return options.onBackup ? 'mindmate.backupServerFailed' : 'mindmate.noReply'
  }

  const text = (raw ?? '').trim()
  const status = options.httpStatus ?? (text ? statusFromText(text) : undefined)
  if (status === 502 || status === 503 || status === 504 || (text && isUpstreamPhrase(text))) {
    return outageKey(options.onBackup)
  }
  if (text && BROWSER_NETWORK.has(text.toLowerCase())) {
    return options.hasPartial ? 'mindmate.replyCutOff' : 'mindmate.networkRetry'
  }
  if (errorType === 'internal_error' || (text && isOurServerError(text)) || status === 500) {
    return options.hasPartial ? 'mindmate.replyCutOff' : 'mindmate.serviceRetry'
  }
  if (!text) {
    return options.hasPartial ? 'mindmate.replyCutOff' : 'mindmate.serviceRetry'
  }
  return null
}
