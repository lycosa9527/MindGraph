/**
 * Lets the AI content-level store persist preferences without importing
 * the auth store. Auth is already in the main graph (App.vue and many
 * others), so a dynamic import cannot move it into another chunk.
 */
import type { AiContentLevelId } from '@/config/aiContentLevels'

type AiContentLevelAuthBridge = {
  isAuthenticated: () => boolean
  patchAiContentLevel: (level: AiContentLevelId) => void
}

let bridge: AiContentLevelAuthBridge | null = null

export function registerAiContentLevelAuthBridge(next: AiContentLevelAuthBridge): void {
  bridge = next
}

export function isAiContentLevelAuthAuthenticated(): boolean {
  return bridge?.isAuthenticated() ?? false
}

export function patchAuthPersistedAiContentLevel(level: AiContentLevelId): void {
  bridge?.patchAiContentLevel(level)
}
