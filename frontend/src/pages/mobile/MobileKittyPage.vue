<script setup lang="ts">
/**
 * MobileKittyPage — Full-screen voice assistant (Doubao-style) from the mobile hub.
 * Uses Pinia diagram context when the user arrived from the mobile canvas (or any route
 * that left the diagram store populated); otherwise a minimal landing stub.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { Camera, ChevronLeft, Keyboard, Loader2, Mic, MicOff } from 'lucide-vue-next'

import KittyBlackCatMascot from '@/components/kitty/KittyBlackCatMascot.vue'
import KittyMobileDiagramContextCard from '@/components/kitty/KittyMobileDiagramContextCard.vue'
import { useKittyAgent, useKittyDiagramReviewAnnotationBus, useLanguage, useNotifications } from '@/composables'
import { compressImageFileForKitty } from '@/composables/kitty/compressImageForKitty'
import { useKittyMobileDebugBus } from '@/composables/kitty/useKittyMobileDebugBus'
import { useMobileKittyPairing } from '@/composables/kitty/useMobileKittyPairing'
import { useAuthStore, useFeatureFlagsStore } from '@/stores'

const router = useRouter()
const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const featureFlagsStore = useFeatureFlagsStore()
const { flags } = storeToRefs(featureFlagsStore)
const kittyServerEnabled = computed(() => flags.value?.feature_kitty_agent ?? false)

const showKeyboard = ref(false)
const draft = ref('')
const micDenied = ref(false)
const cameraDenied = ref(false)
const scrollRoot = ref<HTMLElement | null>(null)

const KITTY_DEBUG_MAX = 42
const kittyDebugLines = ref<string[]>([])

function pushKittyDebugLine(prefix: string, detail: string): void {
  const d = new Date()
  const pad = (n: number, w: number) => String(n).padStart(w, '0')
  const stamp = `${pad(d.getHours(), 2)}:${pad(d.getMinutes(), 2)}:${pad(d.getSeconds(), 2)}.${pad(d.getMilliseconds(), 3)}`
  const row = `${stamp} ${prefix} ${detail}`.trim()
  const cur = kittyDebugLines.value
  kittyDebugLines.value =
    cur.length >= KITTY_DEBUG_MAX ? [...cur.slice(-(KITTY_DEBUG_MAX - 1)), row] : [...cur, row]
}

const kitty = useKittyAgent({
  ownerId: 'MobileKittyPage',
  kittyClientLane: 'mobile',
  onError: (err: string) => {
    notify.warning(err)
  },
})

const {
  kittyPairScope,
  mobileKittyContextPreview,
  buildMobileKittyContext,
  scheduleMobileKittyContextSync,
  ensureMobileKittyBootstrap,
} = useMobileKittyPairing(kitty, {
  kittyServerEnabled,
  onDebugLine: pushKittyDebugLine,
})

useKittyMobileDebugBus({
  ownerId: 'MobileKittyPage',
  pushLine: pushKittyDebugLine,
  scheduleContextSync: scheduleMobileKittyContextSync,
})

useKittyDiagramReviewAnnotationBus('MobileKittyPageKittyReviewBus')

const connected = computed(() => kitty.isConnected.value)
const connecting = computed(() => kitty.state.value === 'connecting')
const kittyVoiceState = computed(() => kitty.state.value)

const kittyDiagramCardPrimary = computed(() => {
  const p = mobileKittyContextPreview.value
  const title = p.diagramDisplayTitle !== '' ? p.diagramDisplayTitle : t('mobile.kittyDiagramTitleEmpty')
  return `${t('mobile.kittyCurrentDiagramLabel')}: ${title}`
})

const kittyDiagramCardMeta = computed(() => {
  const p = mobileKittyContextPreview.value
  const typ = p.diagramType !== '' ? p.diagramType : '—'
  return t('mobile.kittyDiagramMetaLine', { type: typ, id: p.scopeHintShort })
})

const kittyDiagramCardBadge = computed(() => {
  const src = mobileKittyContextPreview.value.hubSource
  if (!src) {
    return null
  }
  if (src === 'live') {
    return t('mobile.kittyHubSourceLive')
  }
  if (src === 'library') {
    return t('mobile.kittyHubSourceLibrary')
  }
  return t('mobile.kittyHubSourceEmpty')
})

const kittyDiagramCardAriaLabel = computed(() => {
  const meta = kittyDiagramCardMeta.value
  const badge = kittyDiagramCardBadge.value
  const bits = [kittyDiagramCardPrimary.value, meta]
  if (badge) {
    bits.push(badge)
  }
  return bits.filter(Boolean).join('. ')
})

let connectInFlight: Promise<boolean> | null = null

async function ensureConnected(): Promise<boolean> {
  if (kitty.isConnected.value) {
    return true
  }
  if (!authStore.isAuthenticated) {
    notify.warning(t('notification.signInToUse'))
    return false
  }
  if (!kittyServerEnabled.value) {
    notify.warning(
      t(
        'mobile.kittyEnableServerHint',
        '请在服务端 .env 中设置 FEATURE_KITTY_AGENT=True 并重启 API。'
      )
    )
    return false
  }
  if (connectInFlight) {
    return connectInFlight
  }
  connectInFlight = (async () => {
    try {
      micDenied.value = false
      await ensureMobileKittyBootstrap()
      await kitty.startConversation(kittyPairScope.value, buildMobileKittyContext())
      return true
    } catch {
      notify.warning(t('mobile.kittyConnectFailed', '连接失败，请检查网络后重试'))
      return false
    } finally {
      connectInFlight = null
    }
  })()
  return connectInFlight
}

watch(
  kittyPairScope,
  async (scope, prev) => {
    if (prev === undefined || scope === prev) {
      return
    }
    pushKittyDebugLine('#scope', `${String(prev).slice(0, 12)} → ${String(scope).slice(0, 12)}`)
    const wasConnected = kitty.isConnected.value
    const wasConnecting = kitty.state.value === 'connecting'
    if (!wasConnected && !wasConnecting) {
      return
    }
    await kitty.stopConversation()
    if (wasConnected) {
      void ensureConnected()
    }
  },
  { flush: 'post' }
)

async function goHome(): Promise<void> {
  await kitty.stopConversation()
  router.push('/m')
}

async function handleDisconnect(): Promise<void> {
  await kitty.stopConversation()
}

/** True when typing in the draft field — Space must stay a space character. */
function isKittyTextInputTarget(): boolean {
  if (!showKeyboard.value || !connected.value) {
    return false
  }
  const el = document.activeElement
  if (!el) {
    return false
  }
  if (el.tagName === 'TEXTAREA') {
    return true
  }
  if (el.tagName !== 'INPUT') {
    return false
  }
  const input = el as HTMLInputElement
  const typ = (input.type ?? 'text').toLowerCase()
  if (typ === 'checkbox' || typ === 'radio' || typ === 'file' || typ === 'button') {
    return false
  }
  return true
}

function isTypingOrContentEditableTarget(ev: Event): boolean {
  const t = ev.target
  if (!(t instanceof Node)) {
    return false
  }
  if (!(t instanceof Element)) {
    return false
  }
  const el = t
  if (el.isContentEditable || el.closest('[contenteditable="true"]')) {
    return true
  }
  const tag = el.tagName
  if (tag === 'TEXTAREA') {
    return true
  }
  if (tag === 'SELECT') {
    return true
  }
  if (tag === 'BUTTON') {
    return true
  }
  if (tag === 'INPUT') {
    return true
  }
  return false
}

/**
 * Kitty mic on this page is **push-to-talk only**:
 * – Hold the circular mic button (pointer down/up, with capture).
 * – Hold Space (keydown/keyup), except while focus is in a typing control.
 * There is **no toggle / click-to-arm** UX; a tap ends as soon as the pointer or key lifts.
 */

/** Primary-button push-to-talk (pointer down = open mic, up/cancel = close). Works with mouse + touch. */
const micHoldPointerId = ref<number | null>(null)

function releaseMicPointer(el: HTMLButtonElement | null, pointerId: number): void {
  if (micHoldPointerId.value !== pointerId) {
    return
  }
  micHoldPointerId.value = null
  if (el) {
    try {
      el.releasePointerCapture(pointerId)
    } catch {
      /* capture already released */
    }
  }
  if (kitty.isVoiceActive.value) {
    kitty.stopVoiceInput()
  }
}

async function onMicPointerDown(ev: PointerEvent): Promise<void> {
  if (!kittyServerEnabled.value || connecting.value || micDenied.value) {
    return
  }
  if (ev.button !== 0) {
    return
  }
  if (micHoldPointerId.value !== null) {
    return
  }
  const el = ev.currentTarget
  if (!(el instanceof HTMLButtonElement) || el.disabled) {
    return
  }

  const pid = ev.pointerId
  micHoldPointerId.value = pid
  try {
    el.setPointerCapture(pid)
  } catch {
    /* capture optional */
  }

  const ok = await ensureConnected()
  if (micHoldPointerId.value !== pid) {
    return
  }
  if (!ok) {
    releaseMicPointer(el, pid)
    return
  }
  try {
    await kitty.startVoiceInput()
    micDenied.value = false
  } catch {
    micDenied.value = true
    releaseMicPointer(el, pid)
    return
  }
  if (micHoldPointerId.value !== pid) {
    kitty.stopVoiceInput()
  }
}

function onMicPointerEnd(ev: PointerEvent): void {
  const el = ev.currentTarget instanceof HTMLButtonElement ? ev.currentTarget : null
  releaseMicPointer(el, ev.pointerId)
}

const spaceDrivingMic = ref(false)
const spacePhysicalDown = ref(false)

async function onKittySpacePushKeyDown(ev: KeyboardEvent): Promise<void> {
  if (ev.code !== 'Space' && ev.key !== ' ') {
    return
  }
  if (ev.repeat || isKittyTextInputTarget()) {
    return
  }
  if (isTypingOrContentEditableTarget(ev)) {
    return
  }
  if (!kittyServerEnabled.value || connecting.value || micDenied.value) {
    return
  }
  if (micHoldPointerId.value !== null || spaceDrivingMic.value || spacePhysicalDown.value) {
    return
  }
  ev.preventDefault()
  spacePhysicalDown.value = true
  try {
    const ok = await ensureConnected()
    if (!spacePhysicalDown.value || micHoldPointerId.value !== null) {
      return
    }
    if (!ok) {
      return
    }
    await kitty.startVoiceInput()
    micDenied.value = false
    if (!spacePhysicalDown.value) {
      kitty.stopVoiceInput()
      return
    }
    spaceDrivingMic.value = true
  } catch {
    micDenied.value = true
  }
}

function onKittySpacePushKeyUp(ev: KeyboardEvent): void {
  if (ev.code !== 'Space' && ev.key !== ' ') {
    return
  }
  spacePhysicalDown.value = false
  if (micHoldPointerId.value !== null) {
    return
  }
  if (!spaceDrivingMic.value) {
    return
  }
  ev.preventDefault()
  spaceDrivingMic.value = false
  if (kitty.isVoiceActive.value) {
    kitty.stopVoiceInput()
  }
}

/**
 * Tab / app background: torn down PT. Do not use ``window.blur`` — it also fires while the
 * browser shows the mic permission prompt, which would clear ``spacePhysicalDown`` and mute
 * immediately after ``startVoiceInput()``.
 */
function handleKittyVisibilityForSpaceMic(): void {
  if (!document.hidden) {
    return
  }
  spacePhysicalDown.value = false
  if (micHoldPointerId.value !== null) {
    return
  }
  if (!spaceDrivingMic.value) {
    return
  }
  spaceDrivingMic.value = false
  if (kitty.isVoiceActive.value) {
    kitty.stopVoiceInput()
  }
}

let kittyMicKbBound = false

function bindKittyMicKeyboard(): void {
  if (kittyMicKbBound || typeof window === 'undefined') {
    return
  }
  kittyMicKbBound = true
  window.addEventListener('keydown', onKittySpacePushKeyDown, true)
  window.addEventListener('keyup', onKittySpacePushKeyUp, true)
  document.addEventListener('visibilitychange', handleKittyVisibilityForSpaceMic)
}

function unbindKittyMicKeyboard(): void {
  if (!kittyMicKbBound || typeof window === 'undefined') {
    return
  }
  kittyMicKbBound = false
  window.removeEventListener('keydown', onKittySpacePushKeyDown, true)
  window.removeEventListener('keyup', onKittySpacePushKeyUp, true)
  document.removeEventListener('visibilitychange', handleKittyVisibilityForSpaceMic)
}

async function sendDraft(): Promise<void> {
  const text = draft.value.trim()
  if (!text) return
  const ok = await ensureConnected()
  if (!ok) return
  kitty.sendTextMessage(text)
  draft.value = ''
  showKeyboard.value = false
}

async function onPickImage(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const ok = await ensureConnected()
  if (!ok) return
  try {
    const b64 = await compressImageFileForKitty(file)
    kitty.sendAppendImage(b64, 'jpeg')
    cameraDenied.value = false
  } catch {
    cameraDenied.value = true
  }
}

onMounted(async () => {
  await featureFlagsStore.fetchFlags()
  if (!authStore.isAuthenticated) {
    router.replace('/m')
    return
  }
  pushKittyDebugLine('#', 'debug log ready')
  bindKittyMicKeyboard()
})

onUnmounted(async () => {
  unbindKittyMicKeyboard()
  spacePhysicalDown.value = false
  if (spaceDrivingMic.value) {
    spaceDrivingMic.value = false
    if (micHoldPointerId.value === null && kitty.isVoiceActive.value) {
      kitty.stopVoiceInput()
    }
  }
  if (micHoldPointerId.value !== null) {
    micHoldPointerId.value = null
    if (kitty.isVoiceActive.value) {
      kitty.stopVoiceInput()
    }
  }
  await kitty.stopConversation()
  if (authStore.isAuthenticated && featureFlagsStore.getFeatureKittyAgent()) {
    fetch(`/api/kitty/cleanup/${encodeURIComponent(kittyPairScope.value)}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    }).catch(() => {})
  }
})
</script>

<template>
  <div
    class="mobile-kitty flex flex-col flex-1 min-h-0 w-full bg-gradient-to-b from-slate-100 via-white to-violet-50/40"
  >
    <header class="flex items-center gap-2 h-12 px-2 bg-white/90 backdrop-blur-md shrink-0">
      <button
        type="button"
        class="flex items-center justify-center w-10 h-10 rounded-xl active:bg-gray-100 text-gray-700"
        aria-label="Back"
        @click="goHome"
      >
        <ChevronLeft
          :size="22"
          class="mg-icon-flip-rtl"
        />
      </button>
      <div class="flex-1 min-w-0 text-center">
        <div class="text-base font-semibold text-gray-900 truncate">
          {{ t('mobile.kittyTitle', 'Kitty 智能体') }}
        </div>
        <div
          v-if="connected"
          class="text-[10px] text-emerald-600 font-medium"
        >
          {{ t('mobile.kittyLive', '实时对话') }}
        </div>
      </div>
      <div
        v-if="connected"
        class="flex items-center gap-1.5 shrink-0"
      >
        <button
          type="button"
          class="flex items-center justify-center w-9 h-9 rounded-full bg-gray-100 text-gray-700 active:bg-gray-200 border border-gray-200/80"
          :class="{ 'ring-2 ring-violet-400 ring-offset-1': showKeyboard }"
          :aria-pressed="showKeyboard"
          :aria-label="t('mobile.kittyKeyboardToggle', '文字输入')"
          @click="showKeyboard = !showKeyboard"
        >
          <Keyboard :size="18" />
        </button>
        <button
          type="button"
          class="text-xs text-gray-500 px-2 py-1 rounded-lg active:bg-gray-100 shrink-0"
          @click="handleDisconnect"
        >
          {{ t('mobile.kittyEnd', '结束') }}
        </button>
      </div>
      <div
        v-else
        class="w-10 shrink-0"
      />
    </header>

    <div
      v-if="authStore.isAuthenticated && !kittyServerEnabled"
      class="shrink-0 mx-3 mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 leading-relaxed"
      role="status"
    >
      {{
        t(
          'mobile.kittyServerDisabledBanner',
          '当前环境未开启 Kitty 语音后端，拍照与语音不可用。开发者请在 server .env 中启用 FEATURE_KITTY_AGENT 并重启。'
        )
      }}
    </div>

    <div
      ref="scrollRoot"
      class="flex-1 min-h-0 overflow-y-auto flex flex-col"
    >
      <div
        class="relative z-[2] flex flex-1 flex-col items-center justify-center text-center px-4 py-8 min-h-0"
      >
        <div
          class="pointer-events-none absolute inset-0 z-0 flex items-center justify-start overflow-hidden px-3 sm:pl-4"
          aria-hidden="true"
        >
          <div
            class="kitty-agent-debug-fog w-full max-w-[min(20rem,80vw)] text-left text-[8px] sm:text-[10px] leading-[1.4] text-slate-700/15 antialiased"
          >
            <div
              v-for="(row, idx) in kittyDebugLines"
              :key="idx"
              class="block w-full overflow-hidden text-ellipsis whitespace-nowrap text-left"
            >
              {{ row }}
            </div>
          </div>
        </div>
        <KittyBlackCatMascot
          class="relative z-[3] mb-2"
          :agent-state="kittyVoiceState"
        />
        <p class="relative z-[3] text-gray-700 text-lg font-medium">
          {{ t('mobile.kittyWelcomeLine', '说说你的想法') }}
        </p>
        <p class="relative z-[3] text-sm text-gray-500 mt-2 leading-relaxed max-w-sm">
          {{ t('mobile.kittyWelcomeSub', '语音随问随答，支持拍照识图 — 像豆包一样用起来') }}
        </p>
        <div
          v-if="connecting"
          class="relative z-[3] flex justify-center items-center gap-2 mt-8 text-gray-500 text-sm"
        >
          <Loader2
            :size="20"
            class="animate-spin"
          />
          {{ t('mobile.kittyConnecting', '正在连接…') }}
        </div>
      </div>
    </div>

    <div class="shrink-0 bg-white/90 backdrop-blur-md safe-pb">
      <div
        v-if="connected && showKeyboard"
        class="flex gap-2 items-center px-4 pt-3 pb-1"
      >
        <input
          v-model="draft"
          type="text"
          class="flex-1 min-w-0 border border-gray-200 rounded-xl px-3 py-2.5 text-sm bg-white"
          :placeholder="t('mobile.kittyInputPlaceholder', '输入消息…')"
          @keydown.enter.prevent="sendDraft"
        />
        <button
          type="button"
          class="shrink-0 px-4 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-medium disabled:opacity-40"
          :disabled="!draft.trim()"
          @click="sendDraft"
        >
          {{ t('mobile.kittySend', '发送') }}
        </button>
      </div>

      <div
        class="flex items-center gap-2 px-3 sm:px-4 py-4 max-w-md mx-auto w-full"
      >
        <label
          class="shrink-0 w-16 h-16 rounded-full bg-gray-100 text-gray-700 flex items-center justify-center shadow-sm border border-gray-200/80"
          :class="{
            'pointer-events-none opacity-40': cameraDenied || !kittyServerEnabled || connecting,
            'active:bg-gray-200 cursor-pointer': !cameraDenied && kittyServerEnabled && !connecting,
          }"
          :aria-label="t('mobile.kittyCameraLabel', '拍照或相册')"
        >
          <Camera :size="26" />
          <input
            type="file"
            accept="image/*"
            capture="environment"
            class="hidden"
            :disabled="!kittyServerEnabled || connecting || cameraDenied"
            @change="onPickImage"
          />
        </label>

        <KittyMobileDiagramContextCard
          class="flex-1 min-w-0 self-center"
          :primary-line="kittyDiagramCardPrimary"
          :meta-line="kittyDiagramCardMeta"
          :source-badge="kittyDiagramCardBadge"
          :aria-label="kittyDiagramCardAriaLabel"
        />

        <button
          type="button"
          class="relative shrink-0 w-16 h-16 rounded-full flex items-center justify-center text-white shadow-md active:scale-95 transition-transform bg-gradient-to-br from-violet-500 to-indigo-600 border border-violet-400/30 disabled:opacity-45 touch-manipulation select-none"
          :disabled="!kittyServerEnabled || connecting || micDenied"
          :aria-label="t('mobile.kittyPushToTalkSpaceAria')"
          :title="t('mobile.kittyPushToTalkSpaceTitle')"
          @pointerdown="onMicPointerDown"
          @pointerup="onMicPointerEnd"
          @pointercancel="onMicPointerEnd"
          @click.prevent
        >
          <Loader2
            v-if="connecting"
            :size="28"
            class="animate-spin text-violet-100"
          />
          <template v-else>
            <MicOff
              v-if="kitty.isVoiceActive"
              :size="30"
            />
            <Mic
              v-else
              :size="30"
            />
          </template>
          <span
            v-if="
              !connecting && (kittyVoiceState === 'listening' || kittyVoiceState === 'speaking')
            "
            class="absolute inset-0 rounded-full ring-4 ring-violet-300/50 animate-pulse pointer-events-none"
            aria-hidden="true"
          />
        </button>
      </div>

      <p
        v-if="micDenied || cameraDenied"
        class="text-center text-xs text-amber-600 pb-2 px-4"
      >
        <span v-if="micDenied">{{ t('mobile.kittyMicDenied', '麦克风不可用') }}</span>
        <span v-if="cameraDenied">{{ t('mobile.kittyCameraDenied', '相机或图片不可用') }}</span>
      </p>
    </div>
  </div>
</template>

<style scoped>
.safe-pb {
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
}

.kitty-agent-debug-fog {
  font-family:
    ui-monospace, 'Cascadia Code', 'Cascadia Mono', 'SFMono-Regular', 'JetBrains Mono', 'Fira Code',
    Consolas, monospace;
}
</style>
