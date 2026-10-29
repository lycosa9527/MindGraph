/**
 * Liveness watch for one seminar socket.
 *
 * Chat frames count as life. Silence longer than the ping line asks the server
 * for a pong. Silence past the dead line reopens the socket so history can
 * fill anything the dead connection missed.
 */

export const COLLAB_SOCKET_WATCH_MS = 5000
export const COLLAB_SOCKET_PING_AFTER_MS = 20000
export const COLLAB_SOCKET_DEAD_AFTER_MS = 30000

export function createCollabSocketHeartbeat(options: {
  sendPing: () => boolean
  reopen: () => void
  isActive: () => boolean
}) {
  let timer: ReturnType<typeof setInterval> | null = null
  let lastInboundAt = 0

  function noteInbound(): void {
    lastInboundAt = Date.now()
  }

  function stop(): void {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function start(): void {
    stop()
    noteInbound()
    timer = setInterval(() => {
      if (!options.isActive()) {
        return
      }
      const silentFor = Date.now() - lastInboundAt
      if (silentFor >= COLLAB_SOCKET_DEAD_AFTER_MS) {
        noteInbound()
        options.reopen()
        return
      }
      if (silentFor >= COLLAB_SOCKET_PING_AFTER_MS) {
        if (!options.sendPing()) {
          noteInbound()
          options.reopen()
        }
      }
    }, COLLAB_SOCKET_WATCH_MS)
  }

  return { noteInbound, start, stop }
}
