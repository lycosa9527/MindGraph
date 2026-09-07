/**
 * Skip POST /channels/initialize after a successful run this tab session.
 * First visit after deploy still posts so retired seed rows can be archived.
 */

/** Bump when initialize must run again (archive retired seeds, default-stream joins). */
export const WORKSHOP_INIT_FLAG_PREFIX = 'workshop:init:v4:'

export function workshopInitFlagKey(userId: number | string): string {
  return `${WORKSHOP_INIT_FLAG_PREFIX}${userId}`
}

export function hasWorkshopInitializedThisSession(
  storage: Pick<Storage, 'getItem'>,
  userId: number | string | null | undefined
): boolean {
  if (userId == null || userId === '') {
    return false
  }
  return storage.getItem(workshopInitFlagKey(userId)) === '1'
}

export function markWorkshopInitializedThisSession(
  storage: Pick<Storage, 'setItem'>,
  userId: number | string
): void {
  storage.setItem(workshopInitFlagKey(userId), '1')
}
