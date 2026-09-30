/**
 * People currently inside a MindMate seminar, shown as header avatars.
 */

export interface SeminarFace {
  userId: number
  name: string
  avatar: string | null
}

export const SEMINAR_FACE_VISIBLE_LIMIT = 4

export function seminarFaceFromPayload(raw: unknown): SeminarFace | null {
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const row = raw as {
    user_id?: unknown
    userId?: unknown
    name?: unknown
    username?: unknown
    avatar?: unknown
  }
  const userId = Number(row.userId ?? row.user_id)
  if (!Number.isFinite(userId) || userId <= 0) {
    return null
  }
  const name = String(row.name ?? row.username ?? '').trim() || `User ${userId}`
  const avatarRaw = row.avatar
  const avatar = typeof avatarRaw === 'string' && avatarRaw.trim() ? avatarRaw.trim() : null
  return { userId, name, avatar }
}

export function seminarFacesFromJoined(raw: unknown, selfFace: SeminarFace | null): SeminarFace[] {
  const faces = Array.isArray(raw)
    ? raw.map((row) => seminarFaceFromPayload(row)).filter((row): row is SeminarFace => row != null)
    : []
  if (faces.length > 0) {
    return dedupeSeminarFaces(faces)
  }
  return selfFace ? [selfFace] : []
}

export function upsertSeminarFace(current: SeminarFace[], incoming: SeminarFace): SeminarFace[] {
  const rest = current.filter((row) => row.userId !== incoming.userId)
  return [...rest, incoming]
}

export function removeSeminarFace(current: SeminarFace[], userId: number): SeminarFace[] {
  if (!Number.isFinite(userId) || userId <= 0) {
    return current
  }
  return current.filter((row) => row.userId !== userId)
}

export function orderSeminarFaces(faces: SeminarFace[], selfId: number): SeminarFace[] {
  return [...faces].sort((left, right) => {
    if (left.userId === selfId) {
      return -1
    }
    if (right.userId === selfId) {
      return 1
    }
    return left.name.localeCompare(right.name)
  })
}

export function splitSeminarFaces(
  faces: SeminarFace[],
  limit = SEMINAR_FACE_VISIBLE_LIMIT
): { visible: SeminarFace[]; overflow: SeminarFace[] } {
  if (faces.length <= limit) {
    return { visible: faces, overflow: [] }
  }
  return { visible: faces.slice(0, limit), overflow: faces.slice(limit) }
}

function dedupeSeminarFaces(faces: SeminarFace[]): SeminarFace[] {
  const seen = new Set<number>()
  const unique: SeminarFace[] = []
  for (const face of faces) {
    if (seen.has(face.userId)) {
      continue
    }
    seen.add(face.userId)
    unique.push(face)
  }
  return unique
}
