/**
 * Structured audit logging for DingTalk bind/unbind pairing in the browser.
 * Mirrors server prefixes ([DingtalkBind:web], [MindBotTool]) for support correlation.
 */
import { reportFrontendLog } from '@/utils/frontendLog'

const PREFIX = '[DingtalkPair:client]'
const SERVER_SOURCE = 'dingtalk_pair'

export type DingTalkPairPurpose = 'bind' | 'unbind'

type PairAuditFields = Record<string, string | number | boolean | undefined | null>

const SERVER_INFO_EVENTS = new Set([
  'modal_open',
  'mint_ok',
  'pairing_completed',
  'session_cancel',
])

const SERVER_WARN_EVENTS = new Set(['mint_failed', 'session_expired', 'room_code_invalid'])

function formatFields(fields: PairAuditFields): string {
  return Object.entries(fields)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(' ')
}

export function pairTokenTail(token: string): string {
  const text = token.trim()
  if (text.length <= 8) {
    return '****'
  }
  return `…${text.slice(-8)}`
}

function formatLine(event: string, fields: PairAuditFields): string {
  const suffix = formatFields(fields)
  return suffix ? `${PREFIX} ${event} ${suffix}` : `${PREFIX} ${event}`
}

function reportToServer(event: string, line: string): void {
  if (SERVER_WARN_EVENTS.has(event)) {
    reportFrontendLog('warn', line, SERVER_SOURCE)
    return
  }
  if (SERVER_INFO_EVENTS.has(event)) {
    reportFrontendLog('info', line, SERVER_SOURCE)
  }
}

export function logPairAudit(
  event: string,
  fields: PairAuditFields = {},
  options?: { reportToServer?: boolean },
): void {
  const line = formatLine(event, fields)
  if (import.meta.env.DEV) {
    if (SERVER_WARN_EVENTS.has(event) || event.includes('failed')) {
      console.warn(line)
    } else {
      console.info(line)
    }
  }
  const shouldReport = options?.reportToServer ?? (
    SERVER_INFO_EVENTS.has(event) || SERVER_WARN_EVENTS.has(event)
  )
  if (shouldReport) {
    reportToServer(event, line)
  }
}
