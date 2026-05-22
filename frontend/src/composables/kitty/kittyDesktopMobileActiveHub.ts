/**
 * Cross-tab cache for ``mobile_active`` driven by the leader tab's desktop wake SSE.
 * Canvas indicator composables subscribe here instead of opening their own poll loops
 * when data is fresh.
 */
import { type DeepReadonly, type Ref, onUnmounted, readonly, ref } from 'vue'

import type { KittyDesktopWakeMobileActive } from '@/composables/kitty/createKittyDesktopWakeStream'

const CHANNEL_NAME = 'mindgraph-kitty-mobile-active-hub'
/** Slightly above SSE heartbeat (25s) so canvas skips REST poll while wake stream is live. */
export const KITTY_MOBILE_ACTIVE_HUB_STALE_MS = 35000

export interface KittyMobileActiveSnapshot {
  active: boolean
  scopes: string[]
  primaryScope: string | null
  updatedAt: number
}

interface HubBroadcastMessage {
  type: 'mobile_active'
  active: boolean
  scopes: string[]
  primaryScope: string | null
  ts: number
}

const emptySnapshot: KittyMobileActiveSnapshot = {
  active: false,
  scopes: [],
  primaryScope: null,
  updatedAt: 0,
}

const snapshot = ref<KittyMobileActiveSnapshot>({ ...emptySnapshot })

let channel: BroadcastChannel | null = null
let subscriberCount = 0

function parseScopes(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return []
  }
  const out: string[] = []
  for (const item of raw) {
    if (typeof item === 'string') {
      const trimmed = item.trim()
      if (trimmed.length > 0 && !out.includes(trimmed)) {
        out.push(trimmed)
      }
    }
  }
  return out
}

function snapshotFromWakePayload(payload: KittyDesktopWakeMobileActive): KittyMobileActiveSnapshot {
  const primary = payload.primary_scope
  return {
    active: payload.active === true,
    scopes: parseScopes(payload.scopes),
    primaryScope:
      typeof primary === 'string' && primary.trim().length > 0 ? primary.trim() : null,
    updatedAt: Date.now(),
  }
}

function applySnapshot(next: KittyMobileActiveSnapshot, broadcast: boolean): void {
  snapshot.value = next
  if (!broadcast || channel == null) {
    return
  }
  const message: HubBroadcastMessage = {
    type: 'mobile_active',
    active: next.active,
    scopes: next.scopes,
    primaryScope: next.primaryScope,
    ts: next.updatedAt,
  }
  channel.postMessage(message)
}

function isHubBroadcastMessage(value: unknown): value is HubBroadcastMessage {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const row = value as Record<string, unknown>
  return row.type === 'mobile_active' && typeof row.ts === 'number'
}

function ensureHubChannel(): void {
  if (channel != null || typeof BroadcastChannel === 'undefined') {
    return
  }
  channel = new BroadcastChannel(CHANNEL_NAME)
  channel.onmessage = (event: MessageEvent) => {
    if (!isHubBroadcastMessage(event.data)) {
      return
    }
    applySnapshot(
      {
        active: event.data.active,
        scopes: event.data.scopes,
        primaryScope: event.data.primaryScope,
        updatedAt: event.data.ts,
      },
      false
    )
  }
}

function releaseHubChannel(): void {
  if (subscriberCount > 0 || channel == null) {
    return
  }
  channel.close()
  channel = null
}

export function isKittyMobileActiveHubFresh(nowMs: number = Date.now()): boolean {
  const updatedAt = snapshot.value.updatedAt
  return updatedAt > 0 && nowMs - updatedAt < KITTY_MOBILE_ACTIVE_HUB_STALE_MS
}

/** Leader SSE / fallback poll publishes here; followers receive via BroadcastChannel. */
export function publishKittyMobileActiveHub(payload: KittyDesktopWakeMobileActive): void {
  ensureHubChannel()
  applySnapshot(snapshotFromWakePayload(payload), true)
}

export function clearKittyMobileActiveHub(): void {
  applySnapshot({ ...emptySnapshot, updatedAt: Date.now() }, true)
}

export function acquireKittyMobileActiveHub(): () => void {
  subscriberCount += 1
  ensureHubChannel()
  return () => {
    subscriberCount = Math.max(0, subscriberCount - 1)
    releaseHubChannel()
  }
}

/** Read-only reactive snapshot; call ``acquireKittyMobileActiveHub`` while subscribed. */
export function useKittyMobileActiveHubSnapshot(): Readonly<
  Ref<DeepReadonly<KittyMobileActiveSnapshot>>
> {
  let release: (() => void) | null = null
  onUnmounted(() => {
    if (release != null) {
      release()
      release = null
    }
  })
  release = acquireKittyMobileActiveHub()
  return readonly(snapshot)
}

export function scopeMatchesKittyMobileActive(
  scope: string,
  mobile: Pick<KittyMobileActiveSnapshot, 'active' | 'scopes' | 'primaryScope'>
): boolean {
  if (!mobile.active) {
    return false
  }
  if (mobile.scopes.includes(scope)) {
    return true
  }
  return mobile.primaryScope != null && mobile.primaryScope === scope
}
