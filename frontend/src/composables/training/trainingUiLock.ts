/**
 * Open panels the course author can freeze onto a step.
 * A panel registers while it is mounted; lock stores its key on the step.
 */

export interface TrainingUiLockSource {
  key: string
  isOpen: () => boolean
  setOpen: (open: boolean) => void
}

const sources = new Map<string, Set<TrainingUiLockSource>>()
let wanted: string | null = null
let armed: string | null = null

export function registerTrainingUiLock(source: TrainingUiLockSource): () => void {
  const bucket = sources.get(source.key) ?? new Set<TrainingUiLockSource>()
  bucket.add(source)
  sources.set(source.key, bucket)
  if (wanted === source.key) source.setOpen(true)
  return () => {
    bucket.delete(source)
    if (bucket.size === 0) sources.delete(source.key)
  }
}

export function captureOpenTrainingUiLock(): string | null {
  for (const [key, bucket] of sources) {
    for (const source of bucket) {
      if (source.isOpen()) return key
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
    for (const source of bucket) source.setOpen(open)
  }
}

export function releaseTrainingUiLock(): void {
  if (!wanted) return
  applyTrainingUiLock(null)
}
