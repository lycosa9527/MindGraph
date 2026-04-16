/** Shared types for MindBot admin config table + dialog. */

export interface MindbotConfigRow {
  id: number
  organization_id: number
  public_callback_token: string
  dingtalk_robot_code: string
  dingtalk_app_secret_masked: string
  dify_api_key_masked: string
  dingtalk_client_id: string | null
  dingtalk_event_token_set: boolean
  dingtalk_event_aes_key_set: boolean
  dingtalk_event_owner_key: string | null
  dify_api_base_url: string
  dify_timeout_seconds: number
  dify_inputs_json: string | null
  show_chain_of_thought_oto: boolean
  show_chain_of_thought_internal_group: boolean
  show_chain_of_thought_cross_org_group: boolean
  chain_of_thought_max_chars: number
  dingtalk_ai_card_template_id: string | null
  dingtalk_ai_card_param_key: string | null
  dingtalk_ai_card_streaming_max_chars: number
  is_enabled: boolean
}

export interface OrgOption {
  id: number
  name: string
  display_name?: string | null
}

export interface MindbotConfigFormState {
  dingtalk_robot_code: string
  dingtalk_client_id: string
  dingtalk_app_secret: string
  dify_api_base_url: string
  dify_api_key: string
  dify_inputs_json: string
  dify_timeout_seconds: number
  /** Unified UI: saved as all three API booleans. */
  show_chain_of_thought: boolean
  chain_of_thought_max_chars: number
  dingtalk_ai_card_template_id: string
  dingtalk_ai_card_param_key: string
  dingtalk_ai_card_streaming_max_chars: number
  is_enabled: boolean
}
