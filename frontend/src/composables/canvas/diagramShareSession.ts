/**
 * FIFO edit lease for a shared library diagram.
 * Alone: normal autosave. With a later opener: relay spec snapshots.
 */
import { ref } from 'vue'

import { diagramShareTabId } from '@/composables/canvas/diagramShareTab'
import { useDiagramStore } from '@/stores'
import { authFetch } from '@/utils/api'

export const diagramShareRole = ref<'editor' | 'viewer' | null>(null)
export const diagramShareEditorName = ref('')

const HEARTBEAT_MS = 10_000
const SEND_MS = 400

let generation = 0
let activeDiagramId: string | null = null
let viewerCount = 0
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let sendTimer: ReturnType<typeof setInterval> | null = null
let socket: WebSocket | null = null
let lastSent = ''
let socketRetries = 0

interface LeaseResponse {
  role: 'editor' | 'viewer'
  editor_name: string
  viewer_count: number
  skipped: boolean
}

function setReadonly(readonly: boolean): void {
  const diagramStore = useDiagramStore()
  diagramStore.isReadonly = readonly
}

function closeSocket(): void {
  if (sendTimer) {
    clearInterval(sendTimer)
    sendTimer = null
  }
  if (socket) {
    socket.onmessage = null
    socket.onclose = null
    socket.close()
    socket = null
  }
  lastSent = ''
  socketRetries = 0
}

function stopHeartbeat(): void {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

async function postLease(
  diagramId: string,
  action: 'join' | 'leave'
): Promise<LeaseResponse | null> {
  const response = await authFetch(`/api/diagrams/${diagramId}/edit-lease`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, tab_id: diagramShareTabId() }),
  })
  if (!response.ok) return null
  return (await response.json()) as LeaseResponse
}

function sendSpec(): void {
  if (diagramShareRole.value !== 'editor' || viewerCount < 1 || !socket) return
  if (socket.readyState !== WebSocket.OPEN) return
  const spec = useDiagramStore().getSpecForSave()
  if (!spec) return
  const payload = JSON.stringify({ type: 'spec', spec })
  if (payload === lastSent || payload.length > 1_400_000) return
  lastSent = payload
  socket.send(payload)
}

function ensureSendLoop(): void {
  if (diagramShareRole.value === 'editor' && viewerCount > 0 && socket) {
    if (!sendTimer) {
      sendSpec()
      sendTimer = setInterval(sendSpec, SEND_MS)
    }
    return
  }
  if (sendTimer) {
    clearInterval(sendTimer)
    sendTimer = null
  }
}

function applyIncoming(raw: string): void {
  if (diagramShareRole.value !== 'viewer') return
  let message: { type?: string; spec?: Record<string, unknown> }
  try {
    message = JSON.parse(raw) as { type?: string; spec?: Record<string, unknown> }
  } catch {
    return
  }
  if (message.type !== 'spec' || !message.spec) return
  const diagramStore = useDiagramStore()
  if (!diagramStore.type) return
  diagramStore.loadFromSpec(message.spec, diagramStore.type)
}

function openSocket(diagramId: string): void {
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
  ) {
    ensureSendLoop()
    return
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${window.location.host}/api/ws/diagram-share/${diagramId}?tab_id=${encodeURIComponent(diagramShareTabId())}`
  const next = new WebSocket(url)
  socket = next
  next.onmessage = (event) => {
    if (typeof event.data === 'string') applyIncoming(event.data)
  }
  next.onopen = () => {
    socketRetries = 0
    ensureSendLoop()
  }
  next.onclose = (event) => {
    if (socket !== next) return
    socket = null
    const closed = event.code === 1000 || event.code === 4000 || event.code === 4001
    const denied = event.code === 4003 || event.code === 1008
    if (closed || denied || activeDiagramId !== diagramId || socketRetries >= 5) return
    socketRetries += 1
    window.setTimeout(() => {
      if (activeDiagramId === diagramId && !socket) openSocket(diagramId)
    }, 1000)
  }
}

function applyLease(diagramId: string, data: LeaseResponse): void {
  if (data.skipped) {
    diagramShareRole.value = null
    diagramShareEditorName.value = ''
    viewerCount = 0
    setReadonly(false)
    closeSocket()
    return
  }
  diagramShareRole.value = data.role
  diagramShareEditorName.value = data.editor_name
  viewerCount = data.viewer_count
  setReadonly(data.role === 'viewer')
  if (data.role === 'viewer' || data.viewer_count > 0) {
    openSocket(diagramId)
  } else {
    closeSocket()
  }
  ensureSendLoop()
}

async function releaseServer(diagramId: string | null): Promise<void> {
  stopHeartbeat()
  closeSocket()
  diagramShareRole.value = null
  diagramShareEditorName.value = ''
  viewerCount = 0
  setReadonly(false)
  if (!diagramId) return
  try {
    await postLease(diagramId, 'leave')
  } catch {
    // The lease expires if this tab never heartbeats again.
  }
}

export async function leaveDiagramShareSession(): Promise<void> {
  generation += 1
  const diagramId = activeDiagramId
  activeDiagramId = null
  await releaseServer(diagramId)
}

export async function enterDiagramShareSession(diagramId: string): Promise<void> {
  const gen = ++generation
  const previous = activeDiagramId
  activeDiagramId = diagramId
  if (previous && previous !== diagramId) {
    await releaseServer(previous)
  }
  if (gen !== generation) return
  let data: LeaseResponse | null
  try {
    data = await postLease(diagramId, 'join')
  } catch {
    data = null
  }
  if (gen !== generation) return
  if (!data) {
    diagramShareRole.value = null
    setReadonly(false)
    return
  }
  applyLease(diagramId, data)
  if (data.skipped) return
  stopHeartbeat()
  heartbeatTimer = setInterval(() => {
    void (async () => {
      if (activeDiagramId !== diagramId) return
      const next = await postLease(diagramId, 'join')
      if (!next || generation !== gen) return
      applyLease(diagramId, next)
    })()
  }, HEARTBEAT_MS)
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', () => {
    void leaveDiagramShareSession()
  })
}
