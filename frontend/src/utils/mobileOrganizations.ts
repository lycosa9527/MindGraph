/**
 * Mobile organization list — keep only the fields the phone UI uses.
 */

export interface MobileOrganizationRow {
  id: number
  name: string
  invitation_code: string
  user_count: number
}

function asRecord(item: unknown): Record<string, unknown> | null {
  if (item == null || typeof item !== 'object') {
    return null
  }
  return item as Record<string, unknown>
}

type InviteTranslate = (
  key: string,
  named: { orgName: string; siteUrl: string; code: string }
) => string

/**
 * Clipboard text for the mobile invite button — same full share message as desktop.
 */
export function mobileOrgInviteClipboardText(
  translate: InviteTranslate,
  org: { name: string; invitationCode: string },
  siteUrl: string,
  fallbackOrgName: string
): string {
  const code = org.invitationCode.trim()
  if (!code) {
    return ''
  }
  const orgName = org.name.trim() || fallbackOrgName.trim()
  return translate('admin.shareInviteMessage', {
    orgName,
    siteUrl: siteUrl.trim(),
    code,
  })
}

export function parseMobileOrganizations(data: unknown): MobileOrganizationRow[] {
  if (!Array.isArray(data)) {
    return []
  }
  const rows: MobileOrganizationRow[] = []
  for (const item of data) {
    const raw = asRecord(item)
    if (!raw) {
      continue
    }
    const id = Number(raw.id)
    if (!Number.isFinite(id) || id <= 0) {
      continue
    }
    const userCount = Number(raw.user_count)
    rows.push({
      id,
      name: String(raw.name ?? ''),
      invitation_code: String(raw.invitation_code ?? '').trim(),
      user_count: Number.isFinite(userCount) && userCount > 0 ? Math.floor(userCount) : 0,
    })
  }
  return rows
}
