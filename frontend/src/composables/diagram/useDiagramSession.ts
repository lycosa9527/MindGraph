/**
 * Injectable diagram session — canvas/nodes use this instead of assuming a single Pinia store.
 * Editor provides the Pinia diagram store; Showcase provides a readonly createDiagramSession().
 */
import { type InjectionKey, inject, toRef, type Ref } from 'vue'

import { useDiagramStore, type DiagramSession } from '@/stores/diagram'

export const DiagramSessionKey: InjectionKey<DiagramSession> = Symbol('DiagramSession')

/**
 * Resolve the nearest provided diagram session, or the editor Pinia store.
 * Prefer an explicit provide from CanvasPage / DiagramSessionProvider.
 */
export function useDiagramSession(): DiagramSession {
  const injected = inject(DiagramSessionKey, null)
  if (injected) return injected
  return useDiagramStore() as unknown as DiagramSession
}

/**
 * Ref to a session field — works for Pinia stores and reactive preview sessions.
 * Prefer this over storeToRefs(useDiagramSession()).
 */
export function diagramSessionRef<K extends keyof DiagramSession>(
  session: DiagramSession,
  key: K
): Ref<DiagramSession[K]> {
  return toRef(session, key) as Ref<DiagramSession[K]>
}
