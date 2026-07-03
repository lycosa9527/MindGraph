/**
 * Active embedded MindMate collab room on /mindmate (sidebar highlight + navigation).
 */
import { ref } from 'vue'

export const embeddedCollabRoomCode = ref<string | null>(null)

export function setEmbeddedCollabRoomCode(code: string | null): void {
  embeddedCollabRoomCode.value = code
}
