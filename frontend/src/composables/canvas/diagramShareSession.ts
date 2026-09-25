/**
 * FIFO edit lease for a shared library diagram.
 * The open SSE response holds the slot and releases it when the tab disconnects.
 * Spec snapshots still travel on the WebSocket.
 * Remote snapshots stay quiet so they do not reset canvas sessions or get saved back.
 */
import { ref } from 'vue'

import { diagramShareTabId } from '@/composables/canvas/diagramShareTab'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores'
import type { LoadFromSpecOptions } from '@/stores/diagram/types'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { authFetch } from '@/utils/api'

export const diagramShareRole = ref<'editor' | 'viewer' | null>(null)
export const diagramShareEditorName = ref('')

const SEND_MS = 400
const QUIET_LOAD: LoadFromSpecOptions = {
  emitLoaded: false,
  skipFit: true,
  preserveMindMapMeasures: true,
}

let generation = 0
const leaseEpoch = Date.now() * 1000 + Math.floor(Math.random() * 1000)
let activeDiagramId: string | null = null
let viewerCount = 0
let shareEvents: EventSource | null = null
let sendTimer: ReturnType<typeof setInterval> | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let socket: WebSocket | null = null
let lastSent = ''
let socketRetries = 0
let roleApply: Promise<void> = Promise.resolve()

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

function clearReconnect(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function closeSocket(): void {
  clearReconnect()
  if (sendTimer) {
    clearInterval(sendTimer)
    sendTimer = null
  }
  if (socket) {
    socket.onmessage = null
    socket.onopen = null
    socket.onclose = null
    socket.close()
    socket = null
  }
  lastSent = ''
  socketRetries = 0
}

function closeShareEvents(): void {
  const source = shareEvents
  shareEvents = null
  if (!source) return
  source.onmessage = null
  source.onerror = null
  source.close()
}

function clearShareState(): void {
  diagramShareRole.value = null
  diagramShareEditorName.value = ''
  viewerCount = 0
}

function applyQuietSpec(spec: Record<string, unknown>): void {
  const diagramStore = useDiagramStore()
  if (!diagramStore.type) return
  diagramStore.loadFromSpec(spec, diagramStore.type, QUIET_LOAD)
  diagramStore.clearHistory()
  eventBus.emit('diagram:share_snapshot_applied', {})
}

function leaveBody(): string {
  return JSON.stringify({ tab_id: diagramShareTabId(), epoch: leaseEpoch })
}

async function postLeave(diagramId: string): Promise<void> {
  try {
    await authFetch(`/api/diagrams/${diagramId}/edit-lease`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: leaveBody(),
    })
  } catch {
    // A dropped SSE connection leaves on its own after a short grace.
  }
}

function leaveKeepalive(diagramId: string): void {
  void fetch(`/api/diagrams/${diagramId}/edit-lease`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    keepalive: true,
    body: leaveBody(),
  })
}

function sendSpec(): void {
  if (diagramShareRole.value !== 'editor' || viewerCount < 1 || !socket) return
  if (socket.readyState !== WebSocket.OPEN) return
  const spec = useDiagramStore().getSpecForSave()
  if (!spec) return
  const payload = JSON.stringify({ type: 'spec', spec })
  if (payload === lastSent || payload.length > 1_400_000) return
  lastSent = payload
  try {
    socket.send(payload)
  } catch {
    lastSent = ''
  }
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

function applyIncoming(raw: string, diagramId: string, gen: number): void {
  if (gen !== generation || activeDiagramId !== diagramId) return
  if (diagramShareRole.value !== 'viewer') return
  let message: { type?: string; spec?: Record<string, unknown> }
  try {
    message = JSON.parse(raw) as { type?: string; spec?: Record<string, unknown> }
  } catch {
    return
  }
  if (message.type !== 'spec' || !message.spec) return
  applyQuietSpec(message.spec)
}

function openSocket(diagramId: string, gen: number): void {
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
  ) {
    ensureSendLoop()
    return
  }
  clearReconnect()
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${window.location.host}/api/ws/diagram-share/${diagramId}?tab_id=${encodeURIComponent(diagramShareTabId())}`
  const next = new WebSocket(url)
  socket = next
  next.onmessage = (event) => {
    if (socket !== next || typeof event.data !== 'string') return
    applyIncoming(event.data, diagramId, gen)
  }
  next.onopen = () => {
    if (socket !== next) return
    socketRetries = 0
    ensureSendLoop()
  }
  next.onclose = (event) => {
    if (socket !== next) return
    socket = null
    const closed = event.code === 1000 || event.code === 4000 || event.code === 4001
    const denied = event.code === 4003 || event.code === 1008
    if (denied && activeDiagramId === diagramId && generation === gen) {
      lockAfterAccessLoss()
      return
    }
    if (
      closed ||
      denied ||
      activeDiagramId !== diagramId ||
      generation !== gen ||
      socketRetries >= 5
    ) {
      return
    }
    socketRetries += 1
    clearReconnect()
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      if (activeDiagramId === diagramId && generation === gen && !socket) {
        openSocket(diagramId, gen)
      }
    }, 1000)
  }
}

function lockAfterAccessLoss(): void {
  generation += 1
  closeShareEvents()
  closeSocket()
  diagramShareEditorName.value = ''
  viewerCount = 0
  diagramShareRole.value = 'viewer'
  setReadonly(true)
}

async function catchUpFromServer(diagramId: string, gen: number): Promise<'ok' | 'lost' | 'stale'> {
  const result = await useSavedDiagramsStore().getDiagram(diagramId, { force: true })
  if (gen !== generation || activeDiagramId !== diagramId) return 'stale'
  if (!result.ok) {
    if (
      result.reason === 'not_found' ||
      result.reason === 'forbidden' ||
      result.reason === 'unauthenticated'
    ) {
      return 'lost'
    }
    return 'ok'
  }
  applyQuietSpec(result.diagram.spec)
  return 'ok'
}

async function applyLease(diagramId: string, data: LeaseResponse, gen: number): Promise<void> {
  if (gen !== generation || activeDiagramId !== diagramId) return
  if (data.skipped) {
    clearShareState()
    setReadonly(false)
    closeSocket()
    return
  }
  const wasViewer = diagramShareRole.value === 'viewer'
  if (wasViewer && data.role === 'editor') {
    const caughtUp = await catchUpFromServer(diagramId, gen)
    if (caughtUp === 'stale') return
    if (caughtUp === 'lost') {
      lockAfterAccessLoss()
      return
    }
  }
  if (gen !== generation || activeDiagramId !== diagramId) return
  diagramShareRole.value = data.role
  diagramShareEditorName.value = data.editor_name
  viewerCount = data.viewer_count
  setReadonly(data.role === 'viewer')
  if (data.role === 'viewer' || data.viewer_count > 0) {
    openSocket(diagramId, gen)
  } else {
    closeSocket()
  }
  ensureSendLoop()
}

function enqueueRole(diagramId: string, data: LeaseResponse, gen: number): void {
  roleApply = roleApply.then(() => applyLease(diagramId, data, gen)).catch(() => undefined)
}

function abandonLocal(): string | null {
  const diagramId = activeDiagramId
  generation += 1
  activeDiagramId = null
  closeShareEvents()
  closeSocket()
  clearShareState()
  setReadonly(false)
  return diagramId
}

function openShareEvents(diagramId: string, gen: number): void {
  closeShareEvents()
  const params = new URLSearchParams({
    tab_id: diagramShareTabId(),
    epoch: String(leaseEpoch),
  })
  const source = new EventSource(`/api/diagrams/${diagramId}/share-events?${params.toString()}`, {
    withCredentials: true,
  })
  shareEvents = source
  source.onmessage = (event) => {
    if (shareEvents !== source || gen !== generation || activeDiagramId !== diagramId) return
    let message: LeaseResponse & { type?: string }
    try {
      message = JSON.parse(event.data) as LeaseResponse & { type?: string }
    } catch {
      return
    }
    if (message.type === 'replaced') {
      closeShareEvents()
      return
    }
    if (message.type === 'denied') {
      closeShareEvents()
      lockAfterAccessLoss()
      return
    }
    if (message.type !== 'role') return
    enqueueRole(diagramId, message, gen)
  }
}

export async function leaveDiagramShareSession(): Promise<void> {
  const diagramId = abandonLocal()
  if (!diagramId) return
  await postLeave(diagramId)
}

export async function enterDiagramShareSession(diagramId: string): Promise<void> {
  const gen = ++generation
  const previous = activeDiagramId
  activeDiagramId = diagramId
  closeShareEvents()
  closeSocket()
  if (previous && previous !== diagramId) {
    clearShareState()
    setReadonly(false)
    await postLeave(previous)
  }
  if (gen !== generation || activeDiagramId !== diagramId) return
  openShareEvents(diagramId, gen)
}

if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', (event) => {
    if (event.persisted) return
    const diagramId = activeDiagramId
    abandonLocal()
    if (diagramId) leaveKeepalive(diagramId)
  })
  window.addEventListener('pageshow', (event) => {
    if (!event.persisted || !activeDiagramId) return
    void enterDiagramShareSession(activeDiagramId)
  })
}
