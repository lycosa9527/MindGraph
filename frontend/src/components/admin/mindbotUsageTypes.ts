/** MindBot usage event row — matches GET /api/mindbot/admin/configs/:id/usage-events items. */

export interface MindbotUsageEventRow {
  id: number
  organization_id: number
  mindbot_config_id: number | null
  dingtalk_staff_id: string
  sender_nick: string | null
  dingtalk_sender_id: string | null
  dify_user_key: string
  msg_id: string | null
  dingtalk_conversation_id: string | null
  dify_conversation_id: string | null
  error_code: string
  streaming: boolean
  prompt_chars: number
  reply_chars: number
  duration_seconds: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  dingtalk_chat_scope: string | null
  inbound_msg_type: string | null
  conversation_user_turn: number | null
  linked_user_id: number | null
  created_at: string
}

export function isMindbotUsageSuccess(code: string): boolean {
  return code === 'MINDBOT_OK' || code === 'MINDBOT_ACCEPTED'
}

export function mindbotThreadKey(row: MindbotUsageEventRow): string {
  const dt = (row.dingtalk_conversation_id ?? '').trim()
  const df = (row.dify_conversation_id ?? '').trim()
  if (!dt && !df) {
    return `singleton:${row.id}`
  }
  return `${row.dingtalk_staff_id}\u0000${dt}\u0000${df}`
}
