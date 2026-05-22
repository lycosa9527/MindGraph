/** One desktop tab per browser profile polls Kitty desktop pairing (BroadcastChannel). */

const CHANNEL_NAME = 'mindgraph-kitty-desktop-poll-leader'
const LEADER_HEARTBEAT_MS = 2000
const LEADER_STALE_MS = 5500
const INITIAL_CLAIM_DELAY_MS = 120

interface LeaderPingMessage {
  type: 'ping'
  tabId: string
  ts: number
}

interface LeaderResignMessage {
  type: 'resign'
  tabId: string
  ts: number
}

type LeaderChannelMessage = LeaderPingMessage | LeaderResignMessage

function isLeaderPingMessage(value: unknown): value is LeaderPingMessage {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const row = value as Record<string, unknown>
  return row.type === 'ping' && typeof row.tabId === 'string' && typeof row.ts === 'number'
}

function isLeaderResignMessage(value: unknown): value is LeaderResignMessage {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const row = value as Record<string, unknown>
  return row.type === 'resign' && typeof row.tabId === 'string' && typeof row.ts === 'number'
}

function isLeaderChannelMessage(value: unknown): value is LeaderChannelMessage {
  return isLeaderPingMessage(value) || isLeaderResignMessage(value)
}

/**
 * Returns teardown. Invokes ``onChange(true)`` when this tab should poll; ``false`` when follower.
 * Without BroadcastChannel support, always leader.
 */
export function createKittyDesktopPollLeader(onChange: (isLeader: boolean) => void): () => void {
  if (typeof BroadcastChannel === 'undefined') {
    onChange(true)
    return () => {
      onChange(false)
    }
  }

  const tabId = crypto.randomUUID()
  const channel = new BroadcastChannel(CHANNEL_NAME)
  let isLeader = false
  let heartbeatId: ReturnType<typeof setInterval> | null = null
  let staleCheckId: ReturnType<typeof setInterval> | null = null
  let initialClaimTimer: ReturnType<typeof setTimeout> | null = null
  let heardRemoteSinceOpen = false
  let lastRemotePingAt = 0
  let closed = false

  function setLeader(next: boolean): void {
    if (isLeader === next) {
      return
    }
    isLeader = next
    onChange(next)
    if (next) {
      if (heartbeatId == null) {
        heartbeatId = setInterval(() => {
          if (closed) {
            return
          }
          channel.postMessage({ type: 'ping', tabId, ts: Date.now() } satisfies LeaderPingMessage)
        }, LEADER_HEARTBEAT_MS)
      }
      return
    }
    if (heartbeatId != null) {
      clearInterval(heartbeatId)
      heartbeatId = null
    }
  }

  channel.onmessage = (event: MessageEvent) => {
    if (!isLeaderChannelMessage(event.data)) {
      return
    }
    if (event.data.tabId === tabId) {
      return
    }
    if (isLeaderResignMessage(event.data)) {
      heardRemoteSinceOpen = false
      lastRemotePingAt = 0
      tryClaimLeadership()
      return
    }
    heardRemoteSinceOpen = true
    lastRemotePingAt = event.data.ts
    setLeader(false)
  }

  function tryClaimLeadership(): void {
    if (closed) {
      return
    }
    const now = Date.now()
    if (heardRemoteSinceOpen && now - lastRemotePingAt <= LEADER_STALE_MS) {
      return
    }
    setLeader(true)
    channel.postMessage({ type: 'ping', tabId, ts: now } satisfies LeaderPingMessage)
  }

  staleCheckId = setInterval(() => {
    tryClaimLeadership()
  }, LEADER_HEARTBEAT_MS)

  initialClaimTimer = setTimeout(() => {
    initialClaimTimer = null
    tryClaimLeadership()
  }, INITIAL_CLAIM_DELAY_MS)

  return () => {
    closed = true
    if (isLeader) {
      try {
        channel.postMessage({ type: 'resign', tabId, ts: Date.now() } satisfies LeaderResignMessage)
      } catch {
        /* channel may already be closing */
      }
    }
    if (initialClaimTimer != null) {
      clearTimeout(initialClaimTimer)
      initialClaimTimer = null
    }
    channel.close()
    if (heartbeatId != null) {
      clearInterval(heartbeatId)
    }
    if (staleCheckId != null) {
      clearInterval(staleCheckId)
    }
    setLeader(false)
  }
}
