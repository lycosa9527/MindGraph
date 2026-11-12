/**
 * Platform-tier org filter for cross-school seminar invites.
 */
import { authFetch } from '@/utils/api'

export interface SeminarInviteOrgOption {
  id: number
  name: string
  displayName: string
}

interface InviteOrgsPayload {
  items?: Array<{
    id?: number
    name?: string
    display_name?: string
  }>
  can_browse?: boolean
}

export async function loadSeminarInviteOrganizations(): Promise<{
  canBrowse: boolean
  items: SeminarInviteOrgOption[]
}> {
  const response = await authFetch('/api/mindmate/invite-organizations')
  if (!response.ok) {
    return { canBrowse: false, items: [] }
  }
  const data = (await response.json()) as InviteOrgsPayload
  const items = (data.items ?? []).flatMap((row) => {
    const id = Number(row.id)
    if (!Number.isFinite(id) || id <= 0) {
      return []
    }
    const displayName = String(row.display_name || row.name || '').trim() || `Org ${id}`
    return [
      {
        id,
        name: String(row.name || '').trim() || displayName,
        displayName,
      },
    ]
  })
  return {
    canBrowse: Boolean(data.can_browse),
    items,
  }
}
