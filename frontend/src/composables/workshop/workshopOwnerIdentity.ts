/**
 * Workshop host vs guest identity.
 *
 * Owner id is kept after the room code is cleared so a guest cannot
 * autosave the host diagram, and forced-exit still works if the socket
 * drops before the ``kicked`` frame is handled.
 */

export function workshopUserOwnsDiagram(
  ownerId: number | null | undefined,
  userId: string | number | null | undefined,
  roomActive = false
): boolean {
  if (ownerId == null) {
    // Live room, owner not yet echoed: fail closed (do not look like the host).
    return !roomActive
  }
  if (userId == null || userId === '') {
    return false
  }
  return String(ownerId) === String(userId)
}

export function workshopUserIsCollabGuest(
  ownerId: number | null | undefined,
  userId: string | number | null | undefined
): boolean {
  if (ownerId == null || userId == null || userId === '') {
    return false
  }
  return String(ownerId) !== String(userId)
}
