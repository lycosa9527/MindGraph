import type { InjectionKey } from 'vue'

/**
 * Open panels the course author can freeze onto a step.
 * A panel registers while it is mounted; lock stores its key on the step.
 */

export const TRAINING_LOCK_SCOPE: InjectionKey<string> = Symbol('trainingLockScope')

export interface TrainingUiLockSource {
  key: string
  /** Empty scope is the real app. A deck shell passes its own id. */
  scope?: string
  isOpen: () => boolean
  setOpen: (open: boolean) => void
}

const sources = new Map<string, Set<TrainingUiLockSource>>()
const scopeStack: string[] = []
let wanted: string | null = null
let armed: string | null = null

export function pushTrainingLockScope(scope: string): () => void {
  scopeStack.push(scope)
  return () => {
    const index = scopeStack.lastIndexOf(scope)
    if (index >= 0) scopeStack.splice(index, 1)
  }
}

function activeScope(): string {
  return scopeStack[scopeStack.length - 1] || ''
}

function inScope(source: TrainingUiLockSource): boolean {
  const scope = activeScope()
  if (!scope) return !source.scope
  return source.scope === scope
}

export function registerTrainingUiLock(source: TrainingUiLockSource): () => void {
  const bucket = sources.get(source.key) ?? new Set<TrainingUiLockSource>()
  bucket.add(source)
  sources.set(source.key, bucket)
  if (wanted === source.key && inScope(source)) source.setOpen(true)
  return () => {
    bucket.delete(source)
    if (bucket.size === 0) sources.delete(source.key)
  }
}

export function captureOpenTrainingUiLock(): string | null {
  for (const [key, bucket] of sources) {
    for (const source of bucket) {
      if (inScope(source) && source.isOpen()) return key
    }
  }
  return null
}

export function armTrainingUiLock(): void {
  armed = captureOpenTrainingUiLock()
}

export function takeArmedTrainingUiLock(): string | null {
  const key = armed
  armed = null
  return key
}

export function applyTrainingUiLock(key: string | null): void {
  wanted = key || null
  for (const [id, bucket] of sources) {
    const open = id === wanted
    for (const source of bucket) {
      if (inScope(source)) source.setOpen(open)
    }
  }
}

export function releaseTrainingUiLock(): void {
  if (!wanted) return
  applyTrainingUiLock(null)
}
