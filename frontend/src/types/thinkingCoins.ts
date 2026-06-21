export interface ThinkingCoinsSummary {
  balance: number
  eligible: boolean
}

export interface ThinkingCoinEarnTask {
  id: number
  slug: string
  title: string
  subtitle?: string | null
  title_en?: string | null
  subtitle_en?: string | null
  reward_amount: number
  handler_key: string
  action_config: Record<string, unknown>
  completed_today?: boolean
  status_hint?: string | null
}

export interface ThinkingCoinsWallet {
  balance: number
  eligible: boolean
  earn_tasks: ThinkingCoinEarnTask[]
}

export interface ThinkingCoinLedgerItem {
  id: number
  delta: number
  balance_after: number
  reason: string
  ref_type?: string | null
  ref_id?: string | null
  created_at: string
}

export interface ThinkingCoinLedgerResponse {
  items: ThinkingCoinLedgerItem[]
  total: number
  page: number
  limit: number
}

export interface ThinkingCoinSettings {
  signup_grant: number
  daily_earn_cap: number
  cost_mindmate_turn: number
  cost_diagram_gen: number
  cost_canvas_assist: number
}

export interface AdminThinkingCoinTask {
  id: number
  slug: string
  title: string
  subtitle?: string | null
  title_en?: string | null
  subtitle_en?: string | null
  reward_amount: number
  monthly_cap?: number | null
  handler_key: string
  action_config?: Record<string, unknown> | null
  sort_order: number
  is_active: boolean
  is_system: boolean
}
