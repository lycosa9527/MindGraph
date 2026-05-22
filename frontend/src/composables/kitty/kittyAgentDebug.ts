/** Curated Kitty agent debug helpers — hide streaming/noisy WS payloads. */

export function normalizeKittyDebugText(raw: unknown, maxLen = 240): string {
  const text = String(raw ?? '')
    .replace(/\s+/g, ' ')
    .trim()
  if (text.length <= maxLen) {
    return text
  }
  return `${text.slice(0, maxLen - 1)}…`
}

export function formatKittyDiagramUpdateDebug(
  action: string,
  updates: Record<string, unknown>
): string {
  const label = action.trim() !== '' ? action : 'update'
  try {
    const json = JSON.stringify(updates)
    if (json === '{}' || json === '[]') {
      return label
    }
    const compact = json.length > 120 ? `${json.slice(0, 117)}…` : json
    return `${label} ${compact}`
  } catch {
    return label
  }
}

export function formatKittyActionDebug(action: string, params: Record<string, unknown>): string {
  const target =
    params.target ??
    params.new_text ??
    params.message ??
    params.prompt ??
    params.node_id ??
    params.diagram_type
  if (typeof target === 'string' && target.trim() !== '') {
    return normalizeKittyDebugText(target, 120)
  }
  try {
    const json = JSON.stringify(params)
    if (json === '{}' || json === 'undefined') {
      return ''
    }
    return json.length > 120 ? `${json.slice(0, 117)}…` : json
  } catch {
    return ''
  }
}
