/**
 * Diagram write lock — one writer: llm | tool | null.
 * Delegates to Pinia ``useKittySessionStore`` (Kitty session SoT).
 */
import {
  useKittySessionStore,
  type KittyWriteLockHolder,
} from '@/stores/kittySession'

export type DiagramWriteLockHolder = KittyWriteLockHolder

export function getDiagramWriteLockHolder(): DiagramWriteLockHolder {
  return useKittySessionStore().writeLockHolder
}

export function setDiagramWriteLockHolder(holder: DiagramWriteLockHolder): void {
  useKittySessionStore().setWriteLockHolder(holder)
}

export function isDiagramWriteLocked(): boolean {
  return useKittySessionStore().isWriteLocked
}
