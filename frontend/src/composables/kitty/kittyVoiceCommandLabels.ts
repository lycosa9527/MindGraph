/**
 * Human-readable labels for Kitty voice commands on desktop command log.
 */
export function formatKittyVoiceCommandLabel(
  action: string,
  detail: string | undefined,
  t: (key: string, params?: Record<string, unknown>) => string
): string {
  const act = action.trim()
  if (!act) {
    return ''
  }
  const key = `kitty.voiceCommand.${act}`
  const detailText = detail?.trim() ?? ''
  const translated = t(key, { detail: detailText })
  if (translated !== key) {
    return translated
  }
  const base = act.replace(/_/g, ' ')
  if (detailText) {
    return `${base}: ${detailText}`
  }
  return base
}
