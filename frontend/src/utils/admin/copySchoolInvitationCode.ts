/**
 * Copy preformatted school invitation payload to clipboard.
 */
export async function copySchoolInvitationPayload(
  text: string,
  onSuccess: () => void,
  onError: () => void
): Promise<void> {
  const trimmed = text.trim()
  if (!trimmed) {
    return
  }
  try {
    await navigator.clipboard.writeText(trimmed)
    onSuccess()
  } catch {
    onError()
  }
}
