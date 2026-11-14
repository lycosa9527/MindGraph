/**
 * Client-side XXX-XXX codes matching backend online-collab charset.
 * Used so the host can share an invite before the room is created; start
 * then prefers this code when allocating the live room.
 */
const SEMINAR_INVITE_CODE_CHARSET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'
const SEMINAR_INVITE_CODE_PART = 3

function randomPart(): string {
  let out = ''
  for (let i = 0; i < SEMINAR_INVITE_CODE_PART; i += 1) {
    const index = Math.floor(Math.random() * SEMINAR_INVITE_CODE_CHARSET.length)
    out += SEMINAR_INVITE_CODE_CHARSET[index]
  }
  return out
}

export function generateSeminarInviteCode(): string {
  return `${randomPart()}-${randomPart()}`
}
