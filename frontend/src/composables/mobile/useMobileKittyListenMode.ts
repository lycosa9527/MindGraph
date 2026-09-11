/**
 * Mobile Kitty listen mode — PTT default, opt-in half-duplex auto.
 */
import { computed, onUnmounted, ref, watch, type Ref } from 'vue'

import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type KittyListenMode = 'manual' | 'auto'

const LISTEN_MODE_KEY = 'kitty.listenMode'
const DEVICE_ID_KEY = 'kitty.deviceId'

export function isKittyMicSecure(): boolean {
  return typeof window !== 'undefined' && window.isSecureContext
}

export function loadKittyListenMode(): KittyListenMode {
  if (typeof localStorage === 'undefined') {
    return 'manual'
  }
  return localStorage.getItem(LISTEN_MODE_KEY) === 'auto' ? 'auto' : 'manual'
}

export function persistKittyListenMode(mode: KittyListenMode): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  localStorage.setItem(LISTEN_MODE_KEY, mode)
}

export function kittyWebDeviceId(): string {
  if (typeof localStorage === 'undefined') {
    return `web-${safeRandomUUID()}`
  }
  const existing = localStorage.getItem(DEVICE_ID_KEY)
  if (existing && existing.trim()) {
    return existing.trim()
  }
  const created = `web-${safeRandomUUID()}`
  localStorage.setItem(DEVICE_ID_KEY, created)
  return created
}

export function asrCommitModeForListen(mode: KittyListenMode): 'release_only' | 'final_or_stopped' {
  return mode === 'auto' ? 'final_or_stopped' : 'release_only'
}

type FunAsrSlice = {
  listening: Ref<boolean>
  startListening: () => Promise<unknown>
  stopListening: () => void
  blessFromUserActivation: () => void
}

type KittySlice = {
  state: Ref<string>
  isPlaying: Ref<boolean>
  isConnected: Ref<boolean>
  ws: Ref<WebSocket | null>
  stopAudioPlayback: () => void
}

export function useMobileKittyListenMode(options: {
  kitty: KittySlice
  funAsr: FunAsrSlice
  micDenied: Ref<boolean>
  kittyServerEnabled: Ref<boolean>
}) {
  const { kitty, funAsr, micDenied, kittyServerEnabled } = options
  const listenMode = ref<KittyListenMode>(loadKittyListenMode())
  const micInsecure = ref(!isKittyMicSecure())
  const pendingAutoListen = ref(false)
  const asrCommitMode = computed(() => asrCommitModeForListen(listenMode.value))

  function sendHello(): void {
    const socket = kitty.ws.value
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return
    }
    socket.send(
      JSON.stringify({
        type: 'hello',
        listen_mode: listenMode.value,
        firmware: 'web-mobile',
        device_id: kittyWebDeviceId(),
      })
    )
  }

  function sendAbort(reason: 'user_ptt' | 'text_input'): void {
    const socket = kitty.ws.value
    kitty.stopAudioPlayback()
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return
    }
    socket.send(JSON.stringify({ type: 'abort', reason }))
  }

  function setListenMode(mode: KittyListenMode): void {
    listenMode.value = mode
    persistKittyListenMode(mode)
    if (mode === 'manual') {
      pendingAutoListen.value = false
      if (funAsr.listening.value) {
        funAsr.stopListening()
      }
    }
    sendHello()
  }

  function toggleListenMode(): void {
    setListenMode(listenMode.value === 'auto' ? 'manual' : 'auto')
  }

  async function startAutoListen(): Promise<void> {
    if (listenMode.value !== 'auto' || micDenied.value || micInsecure.value) {
      return
    }
    if (!kittyServerEnabled.value || funAsr.listening.value) {
      return
    }
    if (kitty.state.value === 'thinking' || kitty.isPlaying.value) {
      pendingAutoListen.value = true
      return
    }
    funAsr.blessFromUserActivation()
    await funAsr.startListening()
  }

  function onAutoMicTap(): void {
    if (micDenied.value || micInsecure.value || !kittyServerEnabled.value) {
      return
    }
    if (kitty.state.value === 'speaking' || kitty.isPlaying.value) {
      sendAbort('user_ptt')
      pendingAutoListen.value = true
      return
    }
    if (funAsr.listening.value) {
      funAsr.stopListening()
      return
    }
    void startAutoListen()
  }

  watch(
    () => kitty.isConnected.value,
    (ok) => {
      if (ok) {
        sendHello()
      }
    },
    { immediate: true }
  )

  watch(
    () => kitty.isPlaying.value,
    (playing, wasPlaying) => {
      if (listenMode.value !== 'auto') {
        return
      }
      if (wasPlaying && !playing) {
        pendingAutoListen.value = true
      }
    }
  )

  watch(
    [pendingAutoListen, () => kitty.isPlaying.value, () => kitty.state.value],
    ([pending, playing, state]) => {
      if (!pending || listenMode.value !== 'auto') {
        return
      }
      if (playing || state === 'thinking' || state === 'speaking') {
        return
      }
      pendingAutoListen.value = false
      void startAutoListen()
    }
  )

  onUnmounted(() => {
    pendingAutoListen.value = false
  })

  return {
    listenMode,
    asrCommitMode,
    micInsecure,
    setListenMode,
    toggleListenMode,
    onAutoMicTap,
    sendAbort,
    sendHello,
  }
}
