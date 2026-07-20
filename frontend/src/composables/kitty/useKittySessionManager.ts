/**
 * Kitty Session Manager FE facade — alignment snapshot, ingress owner, divergence.
 * Backend SoT: GET /api/kitty/session/{scope}
 */
import { type Ref, computed, onUnmounted, ref, watch } from 'vue'

import { shouldLockDesktopOneSentenceForMobileKitty } from '@/composables/canvasToolbar/desktopOneSentenceMobileKittyLock'
import type { KittyMobileActiveSnapshot } from '@/composables/kitty/kittyDesktopMobileActiveHub'
import type { OneSentencePhase } from '@/stores/oneSentence'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type KittySessionAlignment =
  | 'aligned_library'
  | 'aligned_ephemeral'
  | 'promoting'
  | 'scope_divergence'
  | 'mismatch'
  | 'desktop_only'
  | 'mobile_only'
  | 'no_owner'
  | 'empty'

export type KittyIngressSource = 'asr' | 'text' | 'clarify_choice' | 'ui_create'

export interface KittySessionIngressMeta {
  requestId: string
  ingressSource: KittyIngressSource
  utteranceId?: string
}

export interface KittySessionSnapshotDto {
  user_id: number
  requested_scope: string
  desktop_focus_library_id: string | null
  desktop_focus_updated_at: number | null
  mobile_active: boolean
  mobile_scopes: string[]
  mobile_primary_scope: string | null
  canvas_owner_present: boolean
  alignment: KittySessionAlignment
  ingress_owner: 'mobile' | 'desktop'
  error_code: string | null
}

export interface KittySessionSyncChoice {
  id: 'follow_desktop' | 'open_on_desktop' | 'keep_split'
  mobileScope: string
  desktopScope: string
}

/**
 * Build ingress identity for WS text send. Backend journals on ``type: text``.
 */
export function beginKittySessionIngress(options: {
  requestId?: string
  source: KittyIngressSource
  text: string
  utteranceId?: string
}): KittySessionIngressMeta {
  const requestId = options.requestId?.trim() || safeRandomUUID()
  const utteranceId = options.utteranceId?.trim() || undefined
  return {
    requestId,
    ingressSource: options.source,
    utteranceId,
  }
}

/** Report non-WS ingress (ui_create) or rejected attempts to Session Manager journal. */
export async function reportKittySessionIngress(
  scope: string,
  options: {
    requestId?: string
    source: KittyIngressSource
    text: string
    lane?: 'mobile' | 'desktop'
    utteranceId?: string
    rejected?: boolean
    reason?: string
  }
): Promise<boolean> {
  const id = scope.trim()
  if (!id) {
    return false
  }
  try {
    const res = await fetch(`/api/kitty/session/${encodeURIComponent(id)}/ingress`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: options.requestId,
        ingress_source: options.source,
        text: options.text,
        lane: options.lane,
        utterance_id: options.utteranceId,
        rejected: options.rejected === true,
        reason: options.reason,
      }),
    })
    return res.ok
  } catch {
    return false
  }
}

/** Journal ephemeral → library promote after mobile rebond. */
export async function reportKittySessionPromote(
  libraryId: string,
  fromScope: string,
  lane: 'mobile' | 'desktop' = 'mobile'
): Promise<boolean> {
  const toId = libraryId.trim()
  const fromId = fromScope.trim()
  if (!toId || !fromId || toId === fromId) {
    return false
  }
  try {
    const res = await fetch(`/api/kitty/session/${encodeURIComponent(toId)}/promote`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_scope: fromId, lane }),
    })
    return res.ok
  } catch {
    return false
  }
}

export function shouldLockDesktopIngressForMobileKitty(options: {
  phase: OneSentencePhase
  diagramScope: string | null | undefined
  mobile: Pick<KittyMobileActiveSnapshot, 'active' | 'scopes' | 'primaryScope'>
  /** Optional Session Manager snapshot; when present, prefers ingress_owner. */
  sessionSnapshot?: KittySessionSnapshotDto | null
}): boolean {
  const snap = options.sessionSnapshot
  if (snap != null && snap.requested_scope === (options.diagramScope ?? '').trim()) {
    if (options.phase !== 'edit') {
      return false
    }
    return snap.ingress_owner === 'mobile' && snap.mobile_active
  }
  return shouldLockDesktopOneSentenceForMobileKitty({
    phase: options.phase,
    diagramScope: options.diagramScope,
    mobile: options.mobile,
  })
}

export function detectScopeDivergence(
  snapshot: KittySessionSnapshotDto | null | undefined
): KittySessionSyncChoice | null {
  if (snapshot == null || snapshot.alignment !== 'scope_divergence') {
    return null
  }
  const mobileScope = snapshot.mobile_primary_scope?.trim() ?? ''
  const desktopScope = snapshot.desktop_focus_library_id?.trim() ?? ''
  if (!mobileScope || !desktopScope || mobileScope === desktopScope) {
    return null
  }
  return {
    id: 'keep_split',
    mobileScope,
    desktopScope,
  }
}

export function syncChoicesForDivergence(
  divergence: KittySessionSyncChoice | null
): KittySessionSyncChoice[] {
  if (divergence == null) {
    return []
  }
  const base = {
    mobileScope: divergence.mobileScope,
    desktopScope: divergence.desktopScope,
  }
  return [
    { id: 'follow_desktop', ...base },
    { id: 'open_on_desktop', ...base },
    { id: 'keep_split', ...base },
  ]
}

export async function fetchKittySessionSnapshot(
  scope: string,
  options?: { includeJournal?: boolean }
): Promise<KittySessionSnapshotDto | null> {
  const id = scope.trim()
  if (!id) {
    return null
  }
  const q = options?.includeJournal ? '?include_journal=true' : ''
  try {
    const res = await fetch(`/api/kitty/session/${encodeURIComponent(id)}${q}`, {
      credentials: 'same-origin',
    })
    if (!res.ok) {
      return null
    }
    const data: unknown = await res.json()
    if (typeof data !== 'object' || data === null || !('session' in data)) {
      return null
    }
    const session = (data as { session: unknown }).session
    if (typeof session !== 'object' || session === null) {
      return null
    }
    return session as KittySessionSnapshotDto
  } catch {
    return null
  }
}

/**
 * Page-level Session Manager state (mobile / desktop one-sentence).
 */
export function useKittySessionManager(options: {
  scope: Ref<string>
  enabled: Ref<boolean>
  /** Optional poll interval (ms) while enabled; 0 = no poll. */
  pollIntervalMs?: number
}) {
  const snapshot = ref<KittySessionSnapshotDto | null>(null)
  const lastFetchedScope = ref<string | null>(null)
  const pollMs = options.pollIntervalMs ?? 0
  let pollTimer: ReturnType<typeof setInterval> | null = null
  /** Bumps on each refresh intent so in-flight responses for a prior scope are ignored. */
  let refreshGeneration = 0

  const alignment = computed(() => snapshot.value?.alignment ?? null)
  const ingressOwner = computed(() => snapshot.value?.ingress_owner ?? 'desktop')
  const divergence = computed(() => detectScopeDivergence(snapshot.value))
  const syncChoices = computed(() => syncChoicesForDivergence(divergence.value))

  async function refresh(): Promise<KittySessionSnapshotDto | null> {
    if (!options.enabled.value) {
      refreshGeneration += 1
      snapshot.value = null
      lastFetchedScope.value = null
      return null
    }
    const scope = options.scope.value?.trim() ?? ''
    if (!scope) {
      refreshGeneration += 1
      snapshot.value = null
      lastFetchedScope.value = null
      return null
    }
    const generation = ++refreshGeneration
    const next = await fetchKittySessionSnapshot(scope)
    if (generation !== refreshGeneration) {
      return snapshot.value
    }
    const currentScope = options.scope.value?.trim() ?? ''
    if (!options.enabled.value || currentScope !== scope) {
      return snapshot.value
    }
    snapshot.value = next
    lastFetchedScope.value = scope
    return next
  }

  function stopPoll(): void {
    if (pollTimer != null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function startPoll(): void {
    stopPoll()
    if (pollMs <= 0 || !options.enabled.value) {
      return
    }
    pollTimer = setInterval(() => {
      void refresh()
    }, pollMs)
  }

  watch(
    [options.enabled, options.scope],
    () => {
      void refresh().then(() => startPoll())
    },
    { flush: 'post' }
  )

  onUnmounted(() => {
    stopPoll()
    refreshGeneration += 1
    snapshot.value = null
    lastFetchedScope.value = null
  })

  return {
    snapshot,
    alignment,
    ingressOwner,
    divergence,
    syncChoices,
    lastFetchedScope,
    refresh,
    beginIngress: beginKittySessionIngress,
    reportIngress: reportKittySessionIngress,
    reportPromote: reportKittySessionPromote,
    shouldLockDesktopIngress: shouldLockDesktopIngressForMobileKitty,
  }
}
