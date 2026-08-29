/**
 * Active embedded MindMate collab room on /mindmate (sidebar highlight + navigation).
 */
import { ref } from 'vue'

import { wasMindmateCollabCodeRecentlyEnded } from '@/utils/mindmateCollabSessions'

export const embeddedCollabRoomCode = ref<string | null>(null)

export function setEmbeddedCollabRoomCode(code: string | null): void {
  if (code && wasMindmateCollabCodeRecentlyEnded(code)) {
    return
  }
  embeddedCollabRoomCode.value = code
}
