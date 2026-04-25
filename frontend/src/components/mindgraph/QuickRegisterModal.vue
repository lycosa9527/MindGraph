<script setup lang="ts">
/**
 * Quick registration channel: server-minted token, QR (URL not shown), revoke on close.
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
} from 'element-plus'

import { ChevronDown, Loader2, X } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { usePublicSiteUrl } from '@/composables/core/usePublicSiteUrl'
import { useAuthStore } from '@/stores'
import { authFetch } from '@/utils/api'
import { APP_REFINED_SANS_STACK } from '@/utils/diagramNodeFontStack'

/** Font stack for toolbar + room code (shared with diagramNodeFontStack APP_REFINED_SANS_STACK). */
const quickRegFontFamily = APP_REFINED_SANS_STACK

/**
 * Compact countdown ring (viewBox 0 0 120 120, center 60,60) — small, matches room-key type scale.
 */
const COUNTDOWN_RING_R = 50
const COUNTDOWN_RING_CIRC = 2 * Math.PI * COUNTDOWN_RING_R
const ROOM_KEY_URGENT_THRESHOLD_SEC = 10

const MAX_USES_OPTIONS = [50, 100, 200, 500, 1000] as const

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { publicSiteUrl } = usePublicSiteUrl()

const isAdmin = computed(() => authStore.isAdmin)
const adminOrgs = ref<{ id: number; name: string; display_name?: string }[]>([])
const orgsLoading = ref(false)
const selectedOrgId = ref<number | null>(null)
const token = ref('')
const tokenLoading = ref(false)
const suppressOrgChange = ref(true)
const maxUses = ref(200)
const roomDisplay = ref('')
const roomNextIn = ref(0)
const validUntilUnix = ref(0)
const periodSeconds = ref(30)
const signupsCount = ref(0)
const nowMs = ref(Date.now())
let roomCodePoll: ReturnType<typeof setInterval> | null = null
let roomTick: ReturnType<typeof setInterval> | null = null

const authUrl = computed(() => {
  if (!publicSiteUrl.value || !token.value) {
    return ''
  }
  return `${publicSiteUrl.value}/auth?quick_reg=${encodeURIComponent(token.value)}`
})

const qrSrc = computed(() => {
  const u = authUrl.value
  if (!u) {
    return ''
  }
  return `/api/qrcode?data=${encodeURIComponent(u)}&size=260`
})

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const roomRingProgress = computed(() => {
  if (!validUntilUnix.value || !periodSeconds.value) {
    return 0
  }
  const endMs = validUntilUnix.value * 1000
  const totalMs = periodSeconds.value * 1000
  return Math.max(0, Math.min(1, (endMs - nowMs.value) / totalMs))
})

const countdownRingStrokeDash = computed(
  () => `${roomRingProgress.value * COUNTDOWN_RING_CIRC} ${COUNTDOWN_RING_CIRC}`
)

/** Last N seconds of the period: ring + emphasis turn red. */
const roomKeyRingUrgent = computed(
  () =>
    roomNextIn.value > 0 &&
    roomNextIn.value <= ROOM_KEY_URGENT_THRESHOLD_SEC
)

/** Label for the compact school button when an admin has more than one org. */
const selectedOrgLabel = computed(() => {
  if (selectedOrgId.value == null) {
    return t('auth.quickRegSelectOrg')
  }
  const org = adminOrgs.value.find((o) => o.id === selectedOrgId.value)
  return org ? String(org.display_name || org.name) : t('auth.quickRegSelectOrg')
})

function close() {
  visible.value = false
}

function stopRoomCodeUi() {
  if (roomCodePoll) {
    clearInterval(roomCodePoll)
    roomCodePoll = null
  }
  if (roomTick) {
    clearInterval(roomTick)
    roomTick = null
  }
  roomDisplay.value = ''
  roomNextIn.value = 0
  validUntilUnix.value = 0
  periodSeconds.value = 30
  signupsCount.value = 0
  nowMs.value = Date.now()
}

async function fetchRoomCode() {
  if (!token.value) {
    return
  }
  try {
    const r = await authFetch(
      `/api/auth/quick-register/room-code?channel_token=${encodeURIComponent(token.value)}`,
      { method: 'GET' }
    )
    const j = (await r.json().catch(() => ({}))) as {
      code?: string
      valid_until_unix?: number
      period_seconds?: number
      signups_count?: number
    }
    if (r.ok && typeof j.code === 'string') {
      roomDisplay.value = j.code
      if (typeof j.valid_until_unix === 'number') {
        validUntilUnix.value = j.valid_until_unix
      }
      if (typeof j.period_seconds === 'number' && j.period_seconds > 0) {
        periodSeconds.value = j.period_seconds
      }
      if (typeof j.signups_count === 'number' && j.signups_count >= 0) {
        signupsCount.value = j.signups_count
      }
    }
  } catch {
    /* keep last code */
  }
}

function startRoomCodeUi() {
  stopRoomCodeUi()
  void fetchRoomCode()
  roomCodePoll = setInterval(() => {
    void fetchRoomCode()
  }, 5000)
  const tick = () => {
    nowMs.value = Date.now()
    if (!validUntilUnix.value) {
      roomNextIn.value = 0
      return
    }
    roomNextIn.value = Math.max(0, Math.ceil(validUntilUnix.value - nowMs.value / 1000))
  }
  tick()
  roomTick = setInterval(tick, 100)
}

async function loadAdminOrgs() {
  if (!isAdmin.value) {
    return
  }
  orgsLoading.value = true
  try {
    const r = await authFetch('/api/auth/admin/organizations', { method: 'GET' })
    const data = (await r.json().catch(() => [])) as unknown
    if (!r.ok) {
      notify.error(t('auth.quickRegOrgLoadError'))
      adminOrgs.value = []
      return
    }
    const list = Array.isArray(data) ? data : []
    adminOrgs.value = list as { id: number; name: string; display_name?: string }[]
    if (adminOrgs.value.length > 0) {
      const sid = authStore.user?.schoolId
      const match = sid
        ? adminOrgs.value.find((o) => String(o.id) === String(sid))
        : null
      selectedOrgId.value = match ? match.id : adminOrgs.value[0].id
    } else {
      selectedOrgId.value = null
    }
  } catch {
    notify.error(t('auth.quickRegOrgLoadError'))
  } finally {
    orgsLoading.value = false
  }
}

async function revokeToken(keepAlive = false) {
  const tkn = token.value
  if (!tkn) {
    return
  }
  const body = JSON.stringify({ token: tkn })
  if (keepAlive) {
    void fetch('/api/auth/quick-register/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
      credentials: 'same-origin',
    })
  } else {
    try {
      await authFetch('/api/auth/quick-register/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      })
    } catch {
      /* idempotent */
    }
  }
  token.value = ''
}

async function mintToken() {
  if (isAdmin.value) {
    if (adminOrgs.value.length === 0) {
      await loadAdminOrgs()
    }
    if (selectedOrgId.value == null) {
      notify.error(t('auth.quickRegOrgLoadError'))
      return
    }
  }

  tokenLoading.value = true
  try {
    const payload: {
      organization_id?: number
      channel_type: 'workshop'
      max_uses: number
    } = {
      channel_type: 'workshop',
      max_uses: maxUses.value,
    }
    if (isAdmin.value && selectedOrgId.value != null) {
      payload.organization_id = selectedOrgId.value
    }
    const r = await authFetch('/api/auth/quick-register/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = (await r.json().catch(() => ({}))) as { detail?: string; token?: string }
    if (!r.ok) {
      notify.error(
        (typeof data.detail === 'string' && data.detail) || t('auth.quickRegMintError')
      )
      return
    }
    if (data.token) {
      token.value = data.token
    }
  } catch {
    notify.error(t('auth.quickRegMintError'))
  } finally {
    tokenLoading.value = false
  }
}

async function onAdminOrgChange() {
  if (suppressOrgChange.value) {
    return
  }
  await revokeToken()
  await mintToken()
}

async function onAdminOrgDropdownCommand(cmd: string | number) {
  if (suppressOrgChange.value || tokenLoading.value) {
    return
  }
  const id = typeof cmd === 'number' ? cmd : Number(cmd)
  if (Number.isNaN(id) || id === selectedOrgId.value) {
    return
  }
  selectedOrgId.value = id
  await onAdminOrgChange()
}

async function onMaxUsesRemint() {
  if (suppressOrgChange.value || tokenLoading.value) {
    return
  }
  await revokeToken()
  await mintToken()
}

async function onMaxUsesDropdownCommand(cmd: string | number) {
  const n = typeof cmd === 'number' ? cmd : Number(cmd)
  if (Number.isNaN(n) || n === maxUses.value) {
    return
  }
  maxUses.value = n
  await onMaxUsesRemint()
}

watch(
  () => props.modelValue,
  async (v) => {
    if (v) {
      suppressOrgChange.value = true
      token.value = ''
      if (isAdmin.value) {
        await loadAdminOrgs()
      }
      await mintToken()
      await nextTick()
      suppressOrgChange.value = false
    } else {
      await revokeToken()
    }
  }
)

watch(token, (v) => {
  if (v) {
    startRoomCodeUi()
  } else {
    stopRoomCodeUi()
  }
})

onBeforeUnmount(() => {
  stopRoomCodeUi()
  if (token.value) {
    revokeToken(true)
  }
})
</script>

<template>
  <ElDialog
    v-model="visible"
    :show-close="false"
    width="480px"
    class="intl-share-site-dialog"
    align-center
    append-to-body
  >
    <template #header>
      <div
        class="flex w-full min-w-0 items-center justify-between gap-3 pr-0.5"
      >
        <div class="quick-reg-numeric-typography flex min-w-0 flex-1 items-center gap-2.5">
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-stone-900 text-sm font-semibold leading-none text-white shadow-sm"
            aria-hidden="true"
          >
            M
          </div>
          <span
            class="truncate text-base font-semibold leading-snug tracking-tight text-stone-900 sm:text-[1.0625rem]"
          >{{ t('sidebar.brandTitle') }}</span>
        </div>
        <ElButton
          class="intl-share-site-close -mr-1 shrink-0"
          text
          circle
          :aria-label="t('common.close')"
          @click="close"
        >
          <X
            class="h-5 w-5"
            aria-hidden="true"
          />
        </ElButton>
      </div>
    </template>

    <div class="intl-share-site-body">
      <div class="quick-reg-toolbar quick-reg-numeric-typography w-full">
        <div
          class="flex w-full flex-wrap items-center justify-center gap-x-4 gap-y-2.5"
        >
          <ElDropdown
            v-if="isAdmin && adminOrgs.length > 1"
            trigger="click"
            :disabled="orgsLoading || tokenLoading"
            @command="onAdminOrgDropdownCommand"
          >
            <ElButton
              type="default"
              size="default"
              :loading="orgsLoading && !token"
              class="quick-reg-field-btn !h-9 max-w-[min(16rem,70vw)] !min-w-0 shrink"
            >
              <span class="truncate text-left text-sm">{{ selectedOrgLabel }}</span>
              <ChevronDown
                class="ml-1.5 h-3.5 w-3.5 shrink-0 text-slate-400"
                aria-hidden="true"
              />
            </ElButton>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem
                  v-for="o in adminOrgs"
                  :key="o.id"
                  :command="o.id"
                >
                  {{ o.display_name || o.name }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>

          <div
            class="flex min-w-0 items-center gap-2"
          >
            <span
              class="shrink-0 text-sm font-medium text-slate-600"
            >{{ t('auth.quickRegHeadcount') }}</span>
            <ElDropdown
              trigger="click"
              :disabled="tokenLoading"
              @command="onMaxUsesDropdownCommand"
            >
              <ElButton
                type="default"
                size="default"
                class="quick-reg-field-btn !h-9 min-w-[4.5rem] shrink-0 !px-3"
              >
                <span
                  class="text-sm font-medium tabular-nums text-slate-800"
                >{{ maxUses }}</span>
                <ChevronDown
                  class="ml-1 h-3.5 w-3.5 shrink-0 text-slate-400"
                  aria-hidden="true"
                />
              </ElButton>
              <template #dropdown>
                <ElDropdownMenu>
                  <ElDropdownItem
                    v-for="n in MAX_USES_OPTIONS"
                    :key="n"
                    :command="n"
                  >
                    {{ n }}
                  </ElDropdownItem>
                </ElDropdownMenu>
              </template>
            </ElDropdown>
          </div>
        </div>
      </div>

      <div class="intl-share-site-qr-stage">
        <div
          v-if="tokenLoading"
          class="quick-reg-numeric-typography flex min-h-[220px] flex-col items-center justify-center gap-3 py-12 text-slate-400"
        >
          <Loader2
            :size="36"
            class="animate-spin"
            aria-hidden="true"
          />
          <span class="text-sm font-medium text-slate-500">{{
            t('auth.quickRegSubmitting')
          }}</span>
        </div>
        <div
          v-else
          class="qr-ga-stack"
        >
          <div
            class="qr-ga-wrap quick-reg-qr-aura"
            role="img"
            :aria-label="t('landing.international.shareSiteModalTitle')"
          >
            <div class="intl-share-site-qr-inner">
              <img
                v-if="qrSrc && visible"
                :src="qrSrc"
                alt=""
                width="260"
                height="260"
                class="intl-share-site-qr-img"
                decoding="async"
              />
            </div>
          </div>

          <div
            v-if="roomDisplay"
            class="room-key-outer quick-reg-numeric-typography"
            role="status"
            :aria-label="
              t('auth.quickRegRoomCodeLabel') +
              ' ' +
              roomDisplay +
              ', ' +
              t('auth.quickRegCodeRefreshIn', { s: roomNextIn })
            "
          >
            <div class="room-key-row">
              <p class="room-key-digits text-slate-900">
                {{ roomDisplay }}
              </p>
              <div
                class="room-key-count-ring"
                :class="{ 'room-key-count-ring--urgent': roomKeyRingUrgent }"
                aria-hidden="true"
              >
                <svg
                  class="room-key-count-ring__svg"
                  viewBox="0 0 120 120"
                >
                  <circle
                    class="room-key-count-ring__track"
                    cx="60"
                    cy="60"
                    :r="COUNTDOWN_RING_R"
                    fill="none"
                    transform="rotate(-90 60 60)"
                  />
                  <circle
                    class="room-key-count-ring__progress"
                    cx="60"
                    cy="60"
                    :r="COUNTDOWN_RING_R"
                    fill="none"
                    stroke-linecap="round"
                    :stroke-dasharray="countdownRingStrokeDash"
                    transform="rotate(-90 60 60)"
                  />
                </svg>
                <div class="room-key-count-ring__inner">
                  <span
                    class="room-key-count-ring__num"
                    :class="roomKeyRingUrgent ? 'text-red-600' : 'text-slate-600'"
                  >{{ roomNextIn }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <p
        v-if="!tokenLoading"
        class="quick-reg-numeric-typography w-full max-w-sm px-1 text-center text-sm font-medium leading-snug tracking-tight text-slate-600"
      >
        {{ t('auth.quickRegSessionSignups', { n: signupsCount }) }}
      </p>
    </div>
  </ElDialog>
</template>

<style scoped>
/* Rotating conic border — same technique as MindGraphContainer mindgraph-logo-wrapper; emerald/slate (not blue/stone). */
@property --qr-aura-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.intl-share-site-close {
  color: rgb(148 163 184);
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.intl-share-site-close:hover {
  color: rgb(15 23 42);
  background: rgb(241 245 249) !important;
}

/* Inter + Noto (see eagerFonts) — matches app body, cleaner than generic system UI */
.quick-reg-numeric-typography {
  font-family: v-bind(quickRegFontFamily);
  font-feature-settings: "tnum" 1, "kern" 1;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.quick-reg-numeric-typography :deep(.el-button) {
  font-family: inherit;
  font-feature-settings: inherit;
  font-variant-numeric: inherit;
}

.quick-reg-toolbar {
  margin-bottom: 0.125rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid rgb(241 245 249);
  background: linear-gradient(
    180deg,
    rgb(255 255 255) 0%,
    rgb(248 250 252) 100%
  );
  box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.85);
}

:deep(.quick-reg-field-btn.el-button) {
  border-color: rgb(226 232 240);
  font-weight: 500;
  --el-button-hover-text-color: rgb(15 23 42);
}

:deep(.quick-reg-field-btn.el-button:hover),
:deep(.quick-reg-field-btn.el-button:focus-visible) {
  border-color: rgb(203 213 225);
}

.intl-share-site-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  text-align: center;
}

.intl-share-site-qr-stage {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 4px 0 0;
  min-height: 0;
  align-items: center;
}

.qr-ga-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  width: 100%;
}

.qr-ga-wrap {
  position: relative;
  width: 300px;
  height: 300px;
  max-width: min(300px, 82vw);
  max-height: min(300px, 82vw);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 1.125rem;
  box-shadow:
    0 1px 2px rgb(15 23 42 / 0.04),
    0 12px 32px rgb(15 23 42 / 0.08);
}

.quick-reg-qr-aura::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: 1.125rem;
  padding: 4px;
  --qr-aura-angle: 0deg;
  background: conic-gradient(
    from var(--qr-aura-angle) at 50% 50%,
    #f1f5f9 0deg,
    #cbd5e1 45deg,
    #64748b 90deg,
    #0d9488 130deg,
    #10b981 170deg,
    #34d399 210deg,
    #059669 250deg,
    #94a3b8 295deg,
    #f8fafc 360deg
  );
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  pointer-events: none;
  animation: quick-reg-qr-aura-travel 2.5s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .quick-reg-qr-aura::before {
    animation: none;
    --qr-aura-angle: 200deg;
  }
}

@keyframes quick-reg-qr-aura-travel {
  to {
    --qr-aura-angle: 360deg;
  }
}

.qr-ga-wrap > * {
  position: relative;
  z-index: 1;
}

.intl-share-site-qr-inner {
  position: relative;
  z-index: 1;
  padding: 12px;
  border-radius: 0.875rem;
  overflow: hidden;
  background: var(--el-bg-color, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 0.06);
}

.intl-share-site-qr-img {
  display: block;
  width: 260px;
  height: 260px;
  max-width: min(260px, 68vw);
  max-height: min(260px, 68vw);
  object-fit: contain;
  border-radius: 6px;
}

.room-key-outer {
  width: 100%;
  max-width: 22rem;
  text-align: center;
  padding: 0 0.25rem;
}

.room-key-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 0.6em;
  flex-wrap: nowrap;
  margin: 0 auto;
  font-size: clamp(1.5rem, 4.5vw, 1.95rem);
}

.room-key-digits {
  margin: 0;
  font-size: 1em;
  font-weight: 700;
  letter-spacing: 0.16em;
  line-height: 1;
  flex: 0 0 auto;
  /* Inherits .quick-reg-numeric-typography (same as countdown digits) */
}

/* Countdown ring scales with row; slightly wider than cap height for two-digit seconds. */
.room-key-count-ring {
  position: relative;
  box-sizing: border-box;
  width: 1.38em;
  height: 1.38em;
  flex: 0 0 auto;
}

.room-key-count-ring__svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.room-key-count-ring__track {
  stroke: rgb(226 232 240);
  stroke-width: 6.2;
  transition: stroke 0.3s ease;
}

.room-key-count-ring__progress {
  stroke: rgb(5 150 105);
  stroke-width: 6.2;
  transition:
    stroke 0.3s ease,
    stroke-dasharray 0.1s linear;
}

.room-key-count-ring--urgent .room-key-count-ring__track {
  stroke: rgb(254 202 202);
}

.room-key-count-ring--urgent .room-key-count-ring__progress {
  stroke: rgb(220 38 38);
}

.room-key-count-ring__inner {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  pointer-events: none;
}

.room-key-count-ring__num {
  font-size: 0.66em;
  font-weight: 700;
  line-height: 1;
  transition: color 0.3s ease;
  /* Inherits .quick-reg-numeric-typography */
}

</style>

<style>
.intl-share-site-dialog.el-dialog {
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgb(226 232 240);
  background: rgb(255 255 255);
  box-shadow:
    0 25px 50px -12px rgb(15 23 42 / 0.2),
    0 0 0 1px rgb(15 23 42 / 0.04),
    inset 0 1px 0 rgb(255 255 255 / 0.9);
}

.intl-share-site-dialog .el-dialog__header {
  padding: 1.125rem 1.375rem 1rem;
  margin: 0;
  background: linear-gradient(180deg, rgb(252 252 254) 0%, rgb(255 255 255) 55%);
  border-bottom: none;
}

.intl-share-site-dialog .el-dialog__body {
  padding: 1.25rem 1.375rem 1.5rem;
  background: linear-gradient(
    180deg,
    rgb(255 255 255) 0%,
    rgb(248 250 252) 55%,
    rgb(252 252 254) 100%
  );
}
</style>
