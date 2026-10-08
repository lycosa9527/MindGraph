/**
 * Superadmin LLM control: traffic diagram and live routing overrides.
 */
import { adminFetchJson } from '@/composables/queries/adminApi'

export interface LlmControlLeg {
  id: string
  provider: 'dashscope' | 'volcengine'
  target: string
  target_kind: 'model' | 'endpoint'
  field: string
  tokens: number
  requests: number
  weight: number | null
  app_rpm: number
  provider_rpm: number | null
  provider_tpm: number | null
  quota_kind: 'fixed' | 'dynamic' | 'endpoint'
  shares_app_rpm: boolean
}

export interface LlmControlStrategy {
  id: 'weighted' | 'round_robin' | 'random'
  active: boolean
}

export interface LlmControlRoute {
  id: string
  split: boolean
  legs: LlmControlLeg[]
}

export interface LlmControlField {
  key: string
  kind: 'model' | 'endpoint'
  value: string
  env_value: string
  overridden: boolean
}

export interface LlmControlView {
  redis_ok: boolean
  tokens_ok: boolean
  balancing_enabled: boolean
  strategy: 'weighted' | 'round_robin' | 'random'
  strategies: LlmControlStrategy[]
  weights: { dashscope: number; volcengine: number }
  routes: LlmControlRoute[]
  fields: LlmControlField[]
}

export function fetchLlmControl(signal?: AbortSignal): Promise<LlmControlView> {
  return adminFetchJson<LlmControlView>('/api/auth/admin/llm-control', { signal })
}

export function saveLlmControl(updates: Record<string, string | null>): Promise<LlmControlView> {
  return adminFetchJson<LlmControlView>('/api/auth/admin/llm-control', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates }),
  })
}
