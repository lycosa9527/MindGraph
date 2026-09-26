/**
 * School chart card opened from the organizations list (usage diagram + detail tabs).
 */

export type SchoolDiagramTab = 'usage' | 'teachers' | 'activity' | 'general'
export type SchoolDiagramPeriod = 'today' | 'week' | 'month' | 'total'

export interface SchoolDiagramCard {
  name: string
  id?: number
  invitationCode: string
  display_name?: string
  is_active?: boolean
  user_count?: number
  expires_at?: string | null
  school_tier?: string | null
  extra_member_seats?: number
  teaching_design_template_key?: string | null
  custom_llm_api_type?: string | null
  custom_llm_base_url?: string | null
  custom_llm_api_key_masked?: string | null
  custom_llm_model?: string | null
  dify_api_base_url?: string | null
  dify_api_key_masked?: string | null
  dify_api_base_url_2?: string | null
  dify_api_key_2_masked?: string | null
  dify_active_server?: number
  dify_failover_enabled?: boolean
  dify_timeout_seconds?: number
  dingtalk_ai_card_streaming_max_chars?: number
  show_chain_of_thought?: boolean
  mindmate_agent_name?: string | null
  mindmate_agent_avatar_url?: string | null
  initial_tab: SchoolDiagramTab
  initial_trend_period: SchoolDiagramPeriod
}

function optionalText(value: unknown): string | null | undefined {
  if (value == null) {
    return value as null | undefined
  }
  return String(value)
}

function finiteNumber(value: unknown, fallback: number): number {
  if (value == null || value === '') {
    return fallback
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function showsChainOfThought(row: Record<string, unknown>): boolean {
  return Boolean(
    row.show_chain_of_thought_oto ||
    row.show_chain_of_thought_internal_group ||
    row.show_chain_of_thought_cross_org_group
  )
}

export function schoolDiagramCardFromRow(
  row: Record<string, unknown>,
  options: {
    invitationCode?: string
    initialTab?: SchoolDiagramTab
    initialTrendPeriod?: SchoolDiagramPeriod
  } = {}
): SchoolDiagramCard {
  const id = Number(row.id)
  return {
    name: String(row.name ?? ''),
    id: Number.isFinite(id) && id > 0 ? id : undefined,
    invitationCode: (options.invitationCode ?? '').trim(),
    display_name: optionalText(row.display_name) ?? undefined,
    is_active: row.is_active as boolean | undefined,
    user_count: finiteNumber(row.user_count, 0),
    expires_at: optionalText(row.expires_at),
    school_tier: optionalText(row.school_tier),
    extra_member_seats: finiteNumber(row.extra_member_seats, 0),
    teaching_design_template_key: optionalText(row.teaching_design_template_key) ?? null,
    custom_llm_api_type: optionalText(row.custom_llm_api_type),
    custom_llm_base_url: optionalText(row.custom_llm_base_url),
    custom_llm_api_key_masked: optionalText(row.custom_llm_api_key_masked),
    custom_llm_model: optionalText(row.custom_llm_model),
    dify_api_base_url: optionalText(row.dify_api_base_url),
    dify_api_key_masked: optionalText(row.dify_api_key_masked),
    dify_api_base_url_2: optionalText(row.dify_api_base_url_2),
    dify_api_key_2_masked: optionalText(row.dify_api_key_2_masked),
    dify_active_server: finiteNumber(row.dify_active_server, 1),
    dify_failover_enabled: (row.dify_failover_enabled as boolean | undefined) ?? true,
    dify_timeout_seconds: finiteNumber(row.dify_timeout_seconds, 300),
    dingtalk_ai_card_streaming_max_chars: finiteNumber(
      row.dingtalk_ai_card_streaming_max_chars,
      6500
    ),
    show_chain_of_thought: showsChainOfThought(row),
    mindmate_agent_name: optionalText(row.mindmate_agent_name),
    mindmate_agent_avatar_url: optionalText(row.mindmate_agent_avatar_url),
    initial_tab: options.initialTab ?? 'usage',
    initial_trend_period: options.initialTrendPeriod ?? 'week',
  }
}
