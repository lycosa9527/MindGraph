import { eventBus } from '@/composables/core/useEventBus'
import type { TrainingModalKey } from '@/config/trainingUiTargets'

type TrainingUiHost = {
  openModal: (key: TrainingModalKey) => void
  closeModals: () => void
}

type TrainingModalOpener = {
  open: () => void
  close?: () => void
}

let host: TrainingUiHost | null = null
const openers = new Map<string, TrainingModalOpener>()

export function registerTrainingUiHost(next: TrainingUiHost): () => void {
  host = next
  return () => {
    if (host === next) host = null
  }
}

export function registerTrainingModalOpener(
  key: string,
  opener: TrainingModalOpener
): () => void {
  openers.set(key, opener)
  return () => {
    if (openers.get(key) === opener) openers.delete(key)
  }
}

const HOST_MODALS = new Set<TrainingModalKey>([
  'language-settings',
  'account',
  'thinking-coins',
  'update-log',
  'login',
])

export function openTrainingModal(key: string | null | undefined): boolean {
  if (!key) return false
  const extra = openers.get(key)
  if (extra) {
    extra.open()
    return true
  }
  if (key === 'export-community') {
    eventBus.emit('toolbar:export_requested', { format: 'community' })
    return true
  }
  if (host && HOST_MODALS.has(key as TrainingModalKey)) {
    host.openModal(key as TrainingModalKey)
    return true
  }
  return false
}

export function closeTrainingModals(): void {
  host?.closeModals()
  for (const opener of openers.values()) {
    opener.close?.()
  }
}
