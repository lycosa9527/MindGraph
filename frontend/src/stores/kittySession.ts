/**
 * Kitty session SoT — Hub revision, write lock, ASR/TTS UI flags.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

export type KittyWriteLockHolder = 'llm' | 'tool' | null

export type KittyMutationAckSender = (payload: Record<string, unknown>) => void

export const useKittySessionStore = defineStore('kittySession', () => {
  const hubScopeRevision = ref<number | null>(null)
  const writeLockHolder = ref<KittyWriteLockHolder>(null)
  const ttsEnabled = ref(true)
  const asrListening = ref(false)
  const asrPartialTranscript = ref('')
  /** True while this browser tab holds the Kitty WS (owning tab). */
  const ownsKittySession = ref(false)
  /** Desktop canvas owner ack sink for verified SSE apply (cross-worker). */
  let mutationAckSender: KittyMutationAckSender | null = null
  /** Dedup verified mutation_ids applied via WS or SSE. */
  const appliedMutationIds = new Set<string>()

  const isWriteLocked = computed(() => writeLockHolder.value !== null)

  function setHubScopeRevision(revision: number | null): void {
    hubScopeRevision.value = revision
  }

  function setWriteLockHolder(holder: KittyWriteLockHolder): void {
    writeLockHolder.value = holder
  }

  function setTtsEnabled(enabled: boolean): void {
    ttsEnabled.value = enabled
  }

  function setAsrListening(listening: boolean): void {
    asrListening.value = listening
    if (!listening) {
      asrPartialTranscript.value = ''
    }
  }

  function setAsrPartialTranscript(text: string): void {
    asrPartialTranscript.value = text
  }

  function setOwnsKittySession(owns: boolean): void {
    ownsKittySession.value = owns
  }

  function setMutationAckSender(sender: KittyMutationAckSender | null): void {
    mutationAckSender = sender
  }

  function getMutationAckSender(): KittyMutationAckSender | null {
    return mutationAckSender
  }

  function claimMutationId(mutationId: string): boolean {
    const id = mutationId.trim()
    if (!id || appliedMutationIds.has(id)) {
      return false
    }
    appliedMutationIds.add(id)
    if (appliedMutationIds.size > 64) {
      const first = appliedMutationIds.values().next().value
      if (typeof first === 'string') {
        appliedMutationIds.delete(first)
      }
    }
    return true
  }

  function resetSessionUi(): void {
    hubScopeRevision.value = null
    writeLockHolder.value = null
    asrListening.value = false
    asrPartialTranscript.value = ''
    ownsKittySession.value = false
    mutationAckSender = null
    appliedMutationIds.clear()
  }

  return {
    hubScopeRevision,
    writeLockHolder,
    ttsEnabled,
    asrListening,
    asrPartialTranscript,
    ownsKittySession,
    isWriteLocked,
    setHubScopeRevision,
    setWriteLockHolder,
    setTtsEnabled,
    setAsrListening,
    setAsrPartialTranscript,
    setOwnsKittySession,
    setMutationAckSender,
    getMutationAckSender,
    claimMutationId,
    resetSessionUi,
  }
})
