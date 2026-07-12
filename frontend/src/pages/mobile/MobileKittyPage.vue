<script setup lang="ts">
/**
 * MobileKittyPage — Full-screen Kitty agent from the mobile hub.
 * Fun-ASR voice + one-sentence edit routing + on-page conversation (no side panel).
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { Camera, ChevronLeft, Keyboard, Loader2, Mic } from '@lucide/vue'

import KittyBlackCatMascot from '@/components/kitty/KittyBlackCatMascot.vue'
import KittyIpodClickWheel from '@/components/kitty/KittyIpodClickWheel.vue'
import KittyMobileChatTranscript from '@/components/kitty/KittyMobileChatTranscript.vue'
import KittyMobileDiagramPickerDropdown from '@/components/kitty/KittyMobileDiagramPickerDropdown.vue'
import KittyMobileLlmModelRow from '@/components/kitty/KittyMobileLlmModelRow.vue'
import {
  getDiagramOperations,
  useKittyAgent,
  useKittyDiagramReviewAnnotationBus,
  useLanguage,
  useNotifications,
} from '@/composables'
import { registerKittyDiagramMutationBus } from '@/composables/kitty/registerKittyDiagramMutationBus'
import { hydrateMobileKittyFromLibrary } from '@/composables/kitty/hydrateMobileKittyFromLibrary'
import { hydrateMobileKittyStoreFromBootstrap } from '@/composables/kitty/hydrateMobileKittyStoreFromBootstrap'
import { applyKittyRemoteLlmModel } from '@/composables/kitty/applyKittyRemoteLlmModel'
import { useKittyFunAsrMic } from '@/composables/kitty/useKittyFunAsrMic'
import { useKittyMobileDebugBus } from '@/composables/kitty/useKittyMobileDebugBus'
import { useKittyMobileHubActionBridge } from '@/composables/kitty/useKittyMobileHubActionBridge'
import { useKittyMobileHubPersist } from '@/composables/kitty/useKittyMobileHubPersist'
import { useKittyMobileLibraryDiagramSelect } from '@/composables/kitty/useKittyMobileLibraryDiagramSelect'
import { useKittyVoiceSelectionBus } from '@/composables/kitty/useKittyVoiceSelectionBus'
import { prepareMobileKittyPhotoCapture } from '@/composables/mobile/prepareMobileKittyPhotoCapture'
import { useMobileKittyChat } from '@/composables/mobile/useMobileKittyChat'
import { useMobileKittyMicPtt } from '@/composables/mobile/useMobileKittyMicPtt'
import { useMobileKittyPageLifecycle } from '@/composables/mobile/useMobileKittyPageLifecycle'
import { useMobileKittyPairing } from '@/composables/kitty/useMobileKittyPairing'
import { useKittyDesktopLlmModelPublish } from '@/composables/kitty/useKittyDesktopLlmModelPublish'
import { useMobileKittyLiveContextPoll } from '@/composables/kitty/useMobileKittyLiveContextPoll'
import { useAuthStore, useFeatureFlagsStore } from '@/stores'
import type { OneSentenceClarifyChoice } from '@/stores/oneSentence'

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
const isDevBuild = import.meta.env.DEV

const KITTY_DEBUG_MAX = 42
const kittyDebugLines = ref<string[]>([])

function pushKittyDebugLine(prefix: string, detail: string): void {
  if (!import.meta.env.DEV) {
    return
  }
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
registerKittyDiagramMutationBus()

const {
  kittyPairScope,
  kittyPairScopeIsEphemeral,
  kittyPairScopeWarning,
  mobileKittyContextPreview,
  bootstrapPayload,
  buildMobileKittyContext,
  resolveMobileOneSentencePhase,
  scheduleMobileKittyContextSync,
  syncMobileKittyContextNow,
  ensureMobileKittyBootstrap,
  refreshMobileKittyBootstrap,
  hydrateLibraryScopeIfNeeded,
  markUserDiagramOverride,
  startNewEphemeralMindmapSession,
  clearForceEphemeralSession,
  sessionId: mobileKittyEphemeralSessionId,
} = useMobileKittyPairing(kitty, {
  kittyServerEnabled,
  onDebugLine: pushKittyDebugLine,
  onDesktopDiagramFollow: () => {
    notify.info(t('mobile.kittyDesktopDiagramFollowed', 'Switched to the diagram open on desktop'))
  },
})

kitty.registerDiagramContextBuilder(buildMobileKittyContext)

/** Linked = non-ephemeral library diagram (chips, LLM, live hydrate, LLM publish). */
const showDiagramChrome = computed(() => {
  if (kittyPairScopeIsEphemeral.value) {
    return false
  }
  const lib = mobileKittyContextPreview.value.diagramLibraryId?.trim() ?? ''
  return lib !== ''
})

/** Mobile LLM pills → desktop canvas (same PUT + Redis wake as desktop→mobile). */
const mobileLlmPublishScope = computed(() => {
  if (!showDiagramChrome.value) {
    return null
  }
  const scope = kittyPairScope.value?.trim() ?? ''
  return scope !== '' ? scope : null
})
const mobileLlmPublishEnabled = computed(
  () =>
    authStore.isAuthenticated &&
    kittyServerEnabled.value &&
    mobileLlmPublishScope.value != null
)
useKittyDesktopLlmModelPublish({
  enabled: mobileLlmPublishEnabled,
  scopeId: mobileLlmPublishScope,
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
  createNewMindmap: createKittyNewMindmap,
} = useKittyMobileLibraryDiagramSelect({
  scheduleContextSync: scheduleMobileKittyContextSync,
  refreshBootstrap: refreshMobileKittyBootstrap,
  hydrateFromLibrary: hydrateMobileKittyFromLibrary,
  hydrateStoreFromBootstrap: () => {
    const boot = bootstrapPayload.value
    hydrateMobileKittyStoreFromBootstrap(boot?.context, boot?.diagram_type ?? 'circle_map')
    void applyKittyRemoteLlmModel(boot?.context?.selected_llm_model)
  },
  onDebugLine: pushKittyDebugLine,
  onUserDiagramOverride: markUserDiagramOverride,
  startNewEphemeralMindmapSession,
  clearForceEphemeralSession,
})

const connected = computed(() => kitty.isConnected.value)
const connecting = computed(() => kitty.state.value === 'connecting')
const kittyVoiceState = computed(() => kitty.state.value)

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

let connectInFlight: Promise<boolean> | null = null

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
  if (kitty.isConnected.value && kitty.isActive.value) {
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
      // Prefer FE one_sentence panel/phase over bootstrap "none" immediately after start.
      syncMobileKittyContextNow()
      maybeWarnEphemeralKittyScope()
      return kitty.isConnected.value && kitty.isActive.value
    } catch {
      notify.warning(t('mobile.kittyConnectFailed', '连接失败，请检查网络后重试'))
      return false
    } finally {
      connectInFlight = null
    }
  })()
  return connectInFlight
}

async function goHome(): Promise<void> {
  await kitty.stopConversation()
  router.push('/m')
}

async function handleDisconnect(): Promise<void> {
  await kitty.stopConversation()
}

/**
 * Camera / photo capture stub for future LLM OCR ingress.
 * Compresses optionally for readiness; does not call retired Omni append_image.
 */
async function handleMobileKittyPhotoCapture(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const result = await prepareMobileKittyPhotoCapture(file)
  if (!result.ok) {
    if (result.reason === 'compress_failed') {
      cameraDenied.value = true
    }
    return
  }
  cameraDenied.value = false
  // Future: send compressedBase64 to LLM OCR ingress (not Omni append_image).
  void result.compressedBase64
  notify.info(
    t(
      'mobile.kittyPhotoOcrComingSoon',
      'Photo OCR is coming soon. Use hold-to-speak or text to edit the diagram.'
    )
  )
}

const funAsr = useKittyFunAsrMic({
  ws: kitty.ws,
  stopPlayback: kitty.stopAudioPlayback,
  ensureConnected: () => ensureConnected(),
  onError: (code) => {
    if (code === 'mic_denied') {
      micDenied.value = true
      return
    }
    notify.warning(t('canvas.mindMapOneSentence.kittyUnavailable'))
  },
})

const kittyVoiceInputActive = computed(() => funAsr.listening.value)

const chatPhase = computed(() => resolveMobileOneSentencePhase())

const {
  messages: chatMessages,
  editPipelineActive,
  sendDraft,
  selectClarifyChoice,
  bindChatScroll,
} = useMobileKittyChat({
  kitty,
  funAsr,
  diagramScope: kittyPairScope,
  ephemeralSessionId: mobileKittyEphemeralSessionId,
  phase: chatPhase,
  draft,
  ensureConnected,
  buildContext: buildMobileKittyContext,
})

// Chat turns refetch whenever kittyPairScope changes (library follow / pick / ephemeral).
// useMobileKittyChat watches diagramScope → bootstrapChat (shared one-sentence REST store).

const liveContextPollEnabled = computed(
  () =>
    authStore.isAuthenticated &&
    kittyServerEnabled.value &&
    showDiagramChrome.value
)
useMobileKittyLiveContextPoll({
  libraryDiagramId: kittyLibraryDiagramId,
  enabled: liveContextPollEnabled,
  editPipelineActive,
  onDebugLine: pushKittyDebugLine,
})

let scopeReconnectTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => bootstrapPayload.value?.context?.selected_llm_model,
  (model) => {
    if (model === undefined) {
      return
    }
    void applyKittyRemoteLlmModel(model)
  }
)

watch(
  kittyPairScope,
  (scope, prev) => {
    if (prev === undefined || scope === prev) {
      return
    }
    pushKittyDebugLine('#scope', `${String(prev).slice(0, 12)} → ${String(scope).slice(0, 12)}`)

    // Already on this scope's socket — hydrate only, do not tear down WS.
    if (kitty.diagramSessionId.value === scope && kitty.isConnected.value) {
      void hydrateLibraryScopeIfNeeded(scope)
      syncMobileKittyContextNow()
      return
    }

    // Never preempt ASR / edit pipeline with a scope reconnect.
    if (funAsr.listening.value || kitty.isVoiceActive.value || editPipelineActive.value) {
      pushKittyDebugLine('#scope', 'defer reconnect — voice/edit active')
      return
    }

    if (scopeReconnectTimer != null) {
      clearTimeout(scopeReconnectTimer)
    }
    scopeReconnectTimer = setTimeout(() => {
      scopeReconnectTimer = null
      void (async () => {
        if (funAsr.listening.value || kitty.isVoiceActive.value || editPipelineActive.value) {
          return
        }
        await hydrateLibraryScopeIfNeeded(scope)
        const wasConnected = kitty.isConnected.value
        const wasConnecting = kitty.state.value === 'connecting'
        if (!wasConnected && !wasConnecting) {
          return
        }
        if (kitty.diagramSessionId.value === scope && kitty.isConnected.value) {
          syncMobileKittyContextNow()
          return
        }
        flushHubLibraryPersist()
        syncMobileKittyContextNow()
        await kitty.stopConversation()
        if (wasConnected || wasConnecting) {
          void ensureConnected()
        }
      })()
    }, 350)
  },
  { flush: 'post' }
)

const {
  pttPointerActive,
  onKittyMicPointerDown,
  onKittyMicPointerUp,
  bindKittyMicKeyboard,
  teardownMicPtt,
} = useMobileKittyMicPtt({
  funAsr,
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

async function handleSendDraft(): Promise<void> {
  const ok = await sendDraft()
  if (ok) {
    showKeyboard.value = false
  }
}

function handleClarifyChoice(choice: OneSentenceClarifyChoice): void {
  void selectClarifyChoice(choice)
}
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

    <div class="flex-1 min-h-0 overflow-hidden flex flex-col">
      <div
        class="kitty-stage-shell relative z-[2] flex flex-1 flex-col min-h-0 w-full self-stretch"
        :class="{ 'kitty-stage-shell--unlinked': !showDiagramChrome }"
      >
        <!-- Unlinked: large Kitty behind the conversation -->
        <div
          v-if="!showDiagramChrome"
          class="kitty-stage__mascot kitty-stage__mascot--unlinked pointer-events-none absolute inset-x-0 bottom-0 z-[1] flex items-end justify-center"
          aria-hidden="true"
        >
          <KittyBlackCatMascot
            class="kitty-stage__mascot-img kitty-stage__mascot-img--unlinked aspect-auto"
            :agent-state="kittyVoiceState"
          />
        </div>

        <div
          class="relative z-[3] flex flex-1 flex-col px-3 pt-2 pb-1 min-h-0 w-full max-w-lg mx-auto"
        >
          <div
            v-if="isDevBuild && kittyDebugLines.length"
            class="pointer-events-none absolute inset-x-3 top-0 z-0 max-h-12 overflow-hidden opacity-35"
            aria-hidden="true"
          >
            <div
              v-for="(row, idx) in kittyDebugLines.slice(-3)"
              :key="idx"
              class="kitty-agent-debug-fog__line"
            >
              {{ row }}
            </div>
          </div>

          <KittyMobileChatTranscript
            class="kitty-chat-overlay w-full flex-1 min-h-0"
            :messages="chatMessages"
            @select-choice="handleClarifyChoice"
            @bind-scroll="bindChatScroll"
          />

          <div
            v-if="connecting"
            class="relative z-[3] flex justify-center items-center gap-2 py-2 text-gray-500 text-sm shrink-0"
          >
            <Loader2
              :size="18"
              class="animate-spin"
            />
            {{ t('mobile.kittyConnecting', '正在连接…') }}
          </div>
        </div>

        <!-- Linked: slightly larger Kitty + node chips + LLM -->
        <div
          v-if="showDiagramChrome"
          class="kitty-stage relative z-[4] w-full shrink-0 mt-1 flex flex-col items-center justify-end gap-1 px-0 pb-1"
        >
          <div
            class="kitty-stage__mascot kitty-stage__mascot--linked relative flex w-full items-center justify-center pointer-events-none shrink-0 overflow-hidden"
          >
            <KittyBlackCatMascot
              class="kitty-stage__mascot-img kitty-stage__mascot-img--linked aspect-auto"
              :agent-state="kittyVoiceState"
            />
          </div>
          <KittyIpodClickWheel
            class="kitty-stage__wheel w-full"
            :on-selection-change="syncMobileKittyContextNow"
          />
          <KittyMobileLlmModelRow
            v-if="authStore.isAuthenticated && kittyServerEnabled"
            class="kitty-stage__llm px-3"
            :on-model-change="syncMobileKittyContextNow"
          />
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
          @keydown.enter.prevent="handleSendDraft"
        />
        <button
          type="button"
          class="shrink-0 px-4 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-medium disabled:opacity-40"
          :disabled="!draft.trim()"
          @click="handleSendDraft"
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
            @change="handleMobileKittyPhotoCapture"
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
          @create-new="createKittyNewMindmap"
        />
        <div
          v-else
          class="kitty-bottom-controls__center"
          aria-hidden="true"
        />

        <button
          type="button"
          data-kitty-mic-ptt
          class="kitty-side-control kitty-side-control--mic kitty-side-control--mic-ptt"
          :class="{ 'kitty-side-control--mic-hold': kittyVoiceInputActive || pttPointerActive }"
          :disabled="!kittyServerEnabled || connecting || micDenied"
          :aria-label="t('mobile.kittyMicPttAria', '按住说话')"
          :title="t('mobile.kittyMicPttTitle', '按住说话，松开发送')"
          @pointerdown="onKittyMicPointerDown"
          @pointerup="onKittyMicPointerUp"
          @pointercancel="onKittyMicPointerUp"
          @contextmenu.prevent
        >
          <Loader2
            v-if="connecting"
            class="kitty-side-control__icon animate-spin text-violet-100"
          />
          <template v-else>
            <Mic class="kitty-side-control__icon kitty-side-control__icon--mic-ptt" />
            <span class="kitty-mic-ptt-label">
              {{
                kittyVoiceInputActive || pttPointerActive
                  ? t('mobile.kittyReleaseToSend', '松开发送')
                  : t('mobile.kittyHoldToSpeak', '按住说话')
              }}
            </span>
          </template>
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

.kitty-stage-shell--unlinked {
  --kitty-overlay-mascot-h: min(42vh, 280px);
}

.kitty-stage__mascot--linked {
  height: min(11vh, 88px);
}

.kitty-stage__mascot--unlinked {
  height: var(--kitty-overlay-mascot-h);
  padding-bottom: 0.5rem;
}

.kitty-stage__mascot-img--linked {
  height: 100%;
  width: min(112px, 34vw);
  max-height: 100%;
}

.kitty-stage__mascot-img--unlinked {
  height: 100%;
  width: min(220px, 62vw);
  max-height: 100%;
}

.kitty-chat-overlay {
  background: transparent;
}

.kitty-stage-shell--unlinked .kitty-chat-overlay {
  padding-bottom: calc(var(--kitty-overlay-mascot-h) * 0.28);
}

.kitty-bottom-controls {
  --kitty-control-size: clamp(3.25rem, 14vw, 4rem);
  --kitty-control-gap: clamp(0.375rem, 2vw, 0.625rem);
  display: grid;
  grid-template-columns: var(--kitty-control-size) minmax(0, 1fr) minmax(5.5rem, 7.5rem);
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

.kitty-side-control--mic-ptt {
  width: 100%;
  max-width: none;
  height: var(--kitty-control-size);
  border-radius: 9999px;
  flex-direction: row;
  gap: 0.35rem;
  padding: 0 0.65rem;
  justify-self: stretch;
}

.kitty-side-control__icon--mic-ptt {
  width: clamp(1.125rem, 5vw, 1.375rem);
  height: clamp(1.125rem, 5vw, 1.375rem);
}

.kitty-mic-ptt-label {
  font-size: clamp(0.6875rem, 3.2vw, 0.8125rem);
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
  line-height: 1.1;
  user-select: none;
}

.kitty-side-control--mic:active:not(:disabled),
.kitty-side-control--mic-hold:not(:disabled) {
  transform: scale(0.97);
}

.kitty-side-control--mic-hold:not(:disabled) {
  background: linear-gradient(to bottom right, #7c3aed, #3730a3);
  box-shadow:
    0 0 0 4px rgba(196, 181, 253, 0.45),
    0 6px 14px rgba(79, 70, 229, 0.35);
}

.kitty-side-control--mic:disabled {
  opacity: 0.45;
}

.kitty-agent-debug-fog__line {
  display: block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  font-size: 0.5625rem;
  line-height: 1.35;
  font-family: ui-monospace, Consolas, monospace;
  color: rgba(51, 65, 85, 0.55);
}
</style>
