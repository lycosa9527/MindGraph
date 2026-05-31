/**
 * Derived organization privatization state for admin organization tables.
 * Prefer API `is_privatized`; fall back to raw fields for older responses.
 */
export function isOrgPrivatized(row: Record<string, unknown>): boolean {
  if (typeof row.is_privatized === 'boolean') {
    return row.is_privatized
  }
  const agentName = String(row.mindmate_agent_name ?? '').trim()
  const avatarUrl = String(row.mindmate_agent_avatar_url ?? '').trim()
  const hasDedicatedDify =
    Boolean(String(row.dify_api_base_url ?? '').trim()) && Boolean(row.dify_api_key_masked)
  return Boolean(agentName && avatarUrl && hasDedicatedDify)
}

const PRIVATIZED_FILTER_VALUE_YES = 'yes'
const PRIVATIZED_FILTER_VALUE_NO = 'no'

export function buildPrivatizedColumnFilters(
  yesLabel: string,
  noLabel: string
): Array<{ text: string; value: string }> {
  return [
    { text: yesLabel, value: PRIVATIZED_FILTER_VALUE_YES },
    { text: noLabel, value: PRIVATIZED_FILTER_VALUE_NO },
  ]
}

export function filterOrgByPrivatized(value: string, row: Record<string, unknown>): boolean {
  const privatized = isOrgPrivatized(row)
  if (value === PRIVATIZED_FILTER_VALUE_YES) {
    return privatized
  }
  if (value === PRIVATIZED_FILTER_VALUE_NO) {
    return !privatized
  }
  return true
}
