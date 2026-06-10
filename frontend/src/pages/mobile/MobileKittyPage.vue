<script setup lang="ts">
/**
 * MobileKittyPage — Full-screen voice assistant (Doubao-style) from the mobile hub.
 * Uses Pinia diagram context when the user arrived from the mobile canvas (or any route
 * that left the diagram store populated); otherwise a minimal landing stub.
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { Camera, ChevronLeft, Keyboard, Loader2, Mic } from '@lucide/vue'

import KittyBlackCatMascot from '@/components/kitty/KittyBlackCatMascot.vue'
import KittyIpodClickWheel from '@/components/kitty/KittyIpodClickWheel.vue'
import KittyMobileDiagramPickerDropdown from '@/components/kitty/KittyMobileDiagramPickerDropdown.vue'
import {
  getDiagramOperations,
  useKittyAgent,
  useKittyDiagramReviewAnnotationBus,
  useLanguage,
  useNotifications,
} from '@/composables'
import { compressImageFileForKitty } from '@/composables/kitty/compressImageForKitty'
import { hydrateMobileKittyFromLibrary } from '@/composables/kitty/hydrateMobileKittyFromLibrary'
import { hydrateMobileKittyStoreFromBootstrap } from '@/composables/kitty/hydrateMobileKittyStoreFromBootstrap'
import { useKittyMobileDebugBus } from '@/composables/kitty/useKittyMobileDebugBus'
import { useKittyMobileHubActionBridge } from '@/composables/kitty/useKittyMobileHubActionBridge'
import { useKittyMobileHubPersist } from '@/composables/kitty/useKittyMobileHubPersist'
import { useKittyMobileLibraryDiagramSelect } from '@/composables/kitty/useKittyMobileLibraryDiagramSelect'
import { useKittyVoiceSelectionBus } from '@/composables/kitty/useKittyVoiceSelectionBus'
import { useMobileKittyMicPtt } from '@/composables/mobile/useMobileKittyMicPtt'
import { useMobileKittyPageLifecycle } from '@/composables/mobile/useMobileKittyPageLifecycle'
import { useMobileKittyPairing } from '@/composables/kitty/useMobileKittyPairing'
import { useAuthStore, useDiagramStore, useFeatureFlagsStore } from '@/stores'

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
  ownerId: 'MobileKittyPage_Agent',
  kittyClientLane: 'mobile',
  onError: (err: string) => {
    notify.warning(err)
  },
})

/** Apply Kitty ``diagram_update`` WS payloads to Pinia (same bridge as canvas pages). */
getDiagramOperations()

const {
  kittyPairScope,
  kittyPairScopeIsEphemeral,
  kittyPairScopeWarning,
  mobileKittyContextPreview,
  bootstrapPayload,
  buildMobileKittyContext,
  scheduleMobileKittyContextSync,
  syncMobileKittyContextNow,
  ensureMobileKittyBootstrap,
  refreshMobileKittyBootstrap,
} = useMobileKittyPairing(kitty, {
  kittyServerEnabled,
  onDebugLine: pushKittyDebugLine,
})

useKittyMobileDebugBus({
  ownerId: 'MobileKittyPage_Debug',
  pushLine: pushKittyDebugLine,
  scheduleContextSync: scheduleMobileKittyContextSync,
})

useKittyDiagramReviewAnnotationBus('MobileKittyPageKittyReviewBus')
useKittyVoiceSelectionBus('MobileKittyPage', {
  onSelectionApplied: syncMobileKittyContextNow,
})
useKittyMobileHubActionBridge(router)

const {
  showPicker: showDiagramPicker,
  selecting: diagramSelecting,
  selectDiagram: selectKittyLibraryDiagram,
} = useKittyMobileLibraryDiagramSelect({
  scheduleContextSync: scheduleMobileKittyContextSync,
  refreshBootstrap: refreshMobileKittyBootstrap,
  hydrateFromLibrary: hydrateMobileKittyFromLibrary,
  hydrateStoreFromBootstrap: () => {
    const boot = bootstrapPayload.value
    hydrateMobileKittyStoreFromBootstrap(boot?.context, boot?.diagram_type ?? 'circle_map')
  },
  onDebugLine: pushKittyDebugLine,
})

const connected = computed(() => kitty.isConnected.value)
const connecting = computed(() => kitty.state.value === 'connecting')
const kittyVoiceState = computed(() => kitty.state.value)
const kittyVoiceInputActive = computed(() => kitty.isVoiceActive.value)

const kittyLibraryDiagramId = computed(() => mobileKittyContextPreview.value.diagramLibraryId)
const kittyDiagramDisplayTitle = computed(() => mobileKittyContextPreview.value.diagramDisplayTitle)

const { flushHubLibraryPersist } = useKittyMobileHubPersist({
  libraryDiagramId: kittyLibraryDiagramId,
  diagramDisplayTitle: kittyDiagramDisplayTitle,
  isConnected: connected,
  buildContext: buildMobileKittyContext,
  updateContext: (ctx, opts) => kitty.updateContext(ctx, opts),
  onDebugLine: pushKittyDebugLine,
})

const kittyDiagramCardPrimary = computed(() => {
  const p = mobileKittyContextPreview.value
  const title =
    p.diagramDisplayTitle !== '' ? p.diagramDisplayTitle : t('mobile.kittyDiagramTitleEmpty')
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

const kittyDiagramCardAccessibleLabel = computed(() => {
  const meta = kittyDiagramCardMeta.value
  const badge = kittyDiagramCardBadge.value
  const bits = [kittyDiagramCardPrimary.value, meta]
  if (badge) {
    bits.push(badge)
  }
  bits.push(t('mobile.kittyDiagramCardTapHint', '点击选择导图'))
  return bits.filter(Boolean).join('. ')
})

const diagramStore = useDiagramStore()
let lastDiagramNodeCount = 0
let connectInFlight: Promise<boolean> | null = null

watch(
  () => diagramStore.data?.nodes?.length ?? 0,
  (count) => {
    if (!kitty.isConnected.value) {
      lastDiagramNodeCount = count
      return
    }
    if (count !== lastDiagramNodeCount) {
      notify.success(t('mobile.kittyDiagramUpdated', 'Diagram updated'))
      lastDiagramNodeCount = count
    }
  }
)

const ephemeralScopeWarned = ref(false)

function maybeWarnEphemeralKittyScope(): void {
  if (!kittyPairScopeIsEphemeral.value || ephemeralScopeWarned.value) {
    return
  }
  const msg = kittyPairScopeWarning.value
  if (!msg) {
    return
  }
  ephemeralScopeWarned.value = true
  notify.warning(msg)
}

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
      maybeWarnEphemeralKittyScope()
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
    flushHubLibraryPersist()
    syncMobileKittyContextNow()
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

const {
  onKittyMicPointerDown,
  onKittyMicPointerUp,
  bindKittyMicKeyboard,
  teardownMicPtt,
} = useMobileKittyMicPtt({
  kitty,
  kittyServerEnabled,
  connecting,
  micDenied,
  showKeyboard,
  connected,
  ensureConnected,
  onMicDenied: () => {
    micDenied.value = true
  },
  onMicAllowed: () => {
    micDenied.value = false
  },
})

useMobileKittyPageLifecycle({
  router,
  authStore,
  featureFlagsStore,
  kitty,
  kittyPairScope,
  bootstrapPayload,
  ensureMobileKittyBootstrap,
  bindKittyMicKeyboard,
  teardownMicPtt,
  pushKittyDebugLine,
  translate: t,
  notifyWarning: (message) => notify.warning(message),
})
</script>

<template>
  <div
    class="mobile-kitty flex flex-col flex-1 min-h-0 w-full bg-gradient-to-b from-slate-100 via-white to-violet-50/40"
  >
    <header class="mobile-kitty-header flex items-center gap-2 h-12 px-2 bg-white/90 backdrop-blur-md shrink-0">
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
        class="relative z-[2] flex flex-1 flex-col items-center px-3 py-4 min-h-0 w-full max-w-lg mx-auto self-stretch"
      >
        <div
          class="pointer-events-none absolute inset-0 z-0 flex items-center justify-start overflow-hidden px-3 sm:pl-4"
          aria-hidden="true"
        >
          <div class="kitty-agent-debug-fog">
            <div
              v-for="(row, idx) in kittyDebugLines"
              :key="idx"
              class="kitty-agent-debug-fog__line"
            >
              {{ row }}
            </div>
          </div>
        </div>
        <div class="kitty-stage relative flex-1 w-full min-h-[min(56vh,520px)] shrink-0">
          <KittyBlackCatMascot
            class="kitty-stage__mascot absolute inset-0 z-[3] flex items-center justify-center pointer-events-none mb-0"
            :agent-state="kittyVoiceState"
          />
          <KittyIpodClickWheel
            class="kitty-stage__wheel absolute inset-[clamp(0.2rem,1.2vw,0.45rem)] z-[4]"
            :on-selection-change="syncMobileKittyContextNow"
          />
        </div>
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

      <div class="kitty-bottom-controls px-3 sm:px-4 py-4 max-w-md mx-auto w-full">
        <label
          class="kitty-side-control kitty-side-control--camera"
          :class="{
            'pointer-events-none opacity-40': cameraDenied || !kittyServerEnabled || connecting,
            'active:bg-gray-200 cursor-pointer': !cameraDenied && kittyServerEnabled && !connecting,
          }"
          :aria-label="t('mobile.kittyCameraLabel', '拍照或相册')"
        >
          <Camera class="kitty-side-control__icon" />
          <input
            type="file"
            accept="image/*"
            capture="environment"
            class="hidden"
            :disabled="!kittyServerEnabled || connecting || cameraDenied"
            @change="onPickImage"
          />
        </label>

        <KittyMobileDiagramPickerDropdown
          v-if="kittyServerEnabled"
          v-model="showDiagramPicker"
          class="kitty-bottom-controls__center"
          :primary-line="kittyDiagramCardPrimary"
          :meta-line="kittyDiagramCardMeta"
          :source-badge="kittyDiagramCardBadge"
          :accessible-label="kittyDiagramCardAccessibleLabel"
          :selecting="diagramSelecting"
          :current-diagram-id="mobileKittyContextPreview.diagramLibraryId"
          :disabled="connecting || diagramSelecting"
          @select="selectKittyLibraryDiagram"
        />
        <div
          v-else
          class="kitty-bottom-controls__center"
          aria-hidden="true"
        />

        <button
          type="button"
          data-kitty-mic-ptt
          class="kitty-side-control kitty-side-control--mic"
          :class="{ 'kitty-side-control--mic-hold': kittyVoiceInputActive || pttPointerActive }"
          :disabled="!kittyServerEnabled || connecting || micDenied"
          :aria-label="t('mobile.kittyMicPttAria', '按住说话')"
          :title="t('mobile.kittyMicPttTitle', '按住麦克风说话，松开发送')"
          @pointerdown="onKittyMicPointerDown"
          @pointerup="onKittyMicPointerUp"
          @pointercancel="onKittyMicPointerUp"
          @contextmenu.prevent
        >
          <Loader2
            v-if="connecting"
            class="kitty-side-control__icon animate-spin text-violet-100"
          />
          <Mic
            v-else
            class="kitty-side-control__icon"
          />
          <span
            v-if="!connecting && (kittyVoiceInputActive || pttPointerActive)"
            class="absolute inset-0 rounded-full ring-4 ring-violet-300/60 animate-pulse pointer-events-none"
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
.mobile-kitty-header {
  padding-top: env(safe-area-inset-top);
}

.safe-pb {
  padding-bottom: max(0.75rem, env(safe-area-inset-bottom));
}

.kitty-bottom-controls {
  --kitty-control-size: clamp(3.25rem, 14vw, 4rem);
  --kitty-control-gap: clamp(0.375rem, 2vw, 0.625rem);
  display: grid;
  grid-template-columns: var(--kitty-control-size) minmax(0, 1fr) var(--kitty-control-size);
  align-items: center;
  column-gap: var(--kitty-control-gap);
}

.kitty-bottom-controls__center {
  min-width: 0;
  width: 100%;
  height: var(--kitty-control-size);
  align-self: center;
}

.kitty-side-control {
  position: relative;
  box-sizing: border-box;
  width: var(--kitty-control-size);
  height: var(--kitty-control-size);
  margin: 0;
  padding: 0;
  border-radius: 9999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  justify-self: center;
  touch-action: manipulation;
  user-select: none;
  transition: transform 0.15s ease;
}

.kitty-side-control__icon {
  width: clamp(1.375rem, 6vw, 1.75rem);
  height: clamp(1.375rem, 6vw, 1.75rem);
  flex-shrink: 0;
}

.kitty-side-control--camera {
  color: #374151;
  background: #f3f4f6;
  border: 1px solid rgba(229, 231, 235, 0.9);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}

.kitty-side-control--mic {
  color: #ffffff;
  border: 1px solid rgba(167, 139, 250, 0.35);
  background: linear-gradient(to bottom right, #8b5cf6, #4f46e5);
  box-shadow: 0 4px 10px rgba(79, 70, 229, 0.28);
}

.kitty-side-control--mic:active:not(:disabled),
.kitty-side-control--mic-hold:not(:disabled) {
  transform: scale(0.95);
}

.kitty-side-control--mic-hold:not(:disabled) {
  box-shadow:
    0 0 0 4px rgba(196, 181, 253, 0.45),
    0 6px 14px rgba(79, 70, 229, 0.35);
}

.kitty-side-control--mic:disabled {
  opacity: 0.45;
}

.kitty-agent-debug-fog {
  width: 100%;
  max-width: min(22rem, 88vw);
  max-height: 100%;
  overflow: hidden;
  text-align: left;
  font-size: clamp(0.5625rem, 2.4vw, 0.6875rem);
  line-height: 1.45;
  font-weight: 500;
  color: rgba(51, 65, 85, 0.52);
  -webkit-font-smoothing: antialiased;
  font-family:
    ui-monospace, 'Cascadia Code', 'Cascadia Mono', 'SFMono-Regular', 'JetBrains Mono', 'Fira Code',
    Consolas, monospace;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.65);
}

.kitty-agent-debug-fog__line {
  display: block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}
</style>
