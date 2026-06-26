<script setup lang="ts">
/**
 * Bluetooth-style DingTalk pairing — show rotating code while MindBot listens.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ElButton, ElDialog } from 'element-plus'

import { Loader2 } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { authFetch } from '@/utils/api'
import {
  logPairAudit,
  pairTokenTail,
  type DingTalkPairPurpose,
} from '@/utils/dingtalkPairAuditLog'

const BIND_TTL_SECONDS = 600
const POLL_MS = 2500
const ROOM_CODE_POLL_MS = 5000

export type DingTalkPairMode = 'bind' | 'unbind'

const props = defineProps<{
  modelValue: boolean
  mode: DingTalkPairMode
  linkedStaffId?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  completed: []
}>()

const { t } = useLanguage()
const notify = useNotifications()

const token = ref('')
const pairCode = ref('')
const pairCodeDisplay = ref('')
const tokenLoading = ref(false)
const expiresAtMs = ref(0)
const validUntilUnix = ref(0)
const nowMs = ref(Date.now())
const completed = ref(false)
const sessionGeneration = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null
let tickTimer: ReturnType<typeof setInterval> | null = null
let roomCodePoll: ReturnType<typeof setInterval> | null = null

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const isUnbind = computed(() => props.mode === 'unbind')

const pairPurpose = computed((): DingTalkPairPurpose => (isUnbind.value ? 'unbind' : 'bind'))

const startEndpoint = computed(() =>
  isUnbind.value ? '/api/auth/dingtalk-bind/unbind/start' : '/api/auth/dingtalk-bind/start'
)

const titleKey = computed(() =>
  isUnbind.value ? 'auth.dingtalkUnbindTitle' : 'auth.dingtalkBindTitle'
)

const instructionsKey = computed(() =>
  isUnbind.value ? 'auth.dingtalkUnbindInstructions' : 'auth.dingtalkBindInstructions'
)

const waitingKey = computed(() =>
  isUnbind.value ? 'auth.dingtalkUnbindPairWaiting' : 'auth.dingtalkBindPairWaiting'
)

const successKey = computed(() =>
  isUnbind.value ? 'auth.dingtalkBindUnbindSuccess' : 'auth.dingtalkBindSuccess'
)

const codeHintKey = computed(() =>
  isUnbind.value ? 'auth.dingtalkUnbindCodeHint' : 'auth.dingtalkBindCodeHint'
)

const expiredKey = computed(() =>
  isUnbind.value ? 'auth.dingtalkUnbindExpiredHint' : 'auth.dingtalkBindExpiredHint'
)

const regenerateKey = computed(() =>
  isUnbind.value ? 'auth.dingtalkUnbindRegenerate' : 'auth.dingtalkBindRegenerate'
)

const secondsLeft = computed(() => {
  if (!expiresAtMs.value) {
    return 0
  }
  return Math.max(0, Math.ceil((expiresAtMs.value - nowMs.value) / 1000))
})

const codeRefreshIn = computed(() => {
  if (!validUntilUnix.value) {
    return 0
  }
  return Math.max(0, Math.ceil(validUntilUnix.value - nowMs.value / 1000))
})

const expired = computed(() => secondsLeft.value <= 0 && !!token.value && !completed.value)

const pairingActive = computed(
  () => !!token.value && !completed.value && !expired.value && !tokenLoading.value
)

function stopTimers() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (tickTimer) {
    clearInterval(tickTimer)
    tickTimer = null
  }
  if (roomCodePoll) {
    clearInterval(roomCodePoll)
    roomCodePoll = null
  }
}

async function cancelPendingToken() {
  try {
    await authFetch('/api/auth/dingtalk-bind/cancel', { method: 'POST' })
    logPairAudit('session_cancel', {
      purpose: pairPurpose.value,
      generation: sessionGeneration.value,
    })
  } catch {
    logPairAudit('session_cancel_failed', {
      purpose: pairPurpose.value,
      generation: sessionGeneration.value,
    }, { reportToServer: false })
  }
}

async function fetchRoomCode(generation: number) {
  if (!token.value || generation !== sessionGeneration.value) {
    return
  }
  try {
    const res = await authFetch(
      `/api/auth/dingtalk-bind/room-code?bind_token=${encodeURIComponent(token.value)}`,
      { method: 'GET' }
    )
    const data = (await res.json().catch(() => ({}))) as {
      code?: string
      code_display?: string
      valid_until_unix?: number
      detail?: { code?: string; message?: string } | string
    }
    if (generation !== sessionGeneration.value) {
      return
    }
    if (res.status === 429) {
      logPairAudit('room_code_rate_limited', {
        purpose: pairPurpose.value,
        generation,
      }, { reportToServer: false })
      return
    }
    if (!res.ok) {
      const detail = data.detail
      const code =
        typeof detail === 'object' && detail && 'code' in detail ? detail.code : undefined
      if (
        code === 'DINGTALK_BIND_NO_PENDING' ||
        code === 'DINGTALK_BIND_TOKEN_FORBIDDEN' ||
        res.status === 400 ||
        res.status === 403
      ) {
        logPairAudit('room_code_invalid', {
          purpose: pairPurpose.value,
          generation,
          reason: code ?? `http_${res.status}`,
          token: pairTokenTail(token.value),
        })
        stopTimers()
        token.value = ''
        pairCode.value = ''
        pairCodeDisplay.value = ''
        notify.warning(t(expiredKey.value))
      }
      return
    }
    const previousCode = pairCode.value
    if (typeof data.code === 'string') {
      pairCode.value = data.code
    }
    if (typeof data.code_display === 'string') {
      pairCodeDisplay.value = data.code_display
    } else if (typeof data.code === 'string' && data.code.length === 6) {
      pairCodeDisplay.value = `${data.code.slice(0, 3)}-${data.code.slice(3)}`
    }
    if (typeof data.valid_until_unix === 'number') {
      validUntilUnix.value = data.valid_until_unix
    }
    if (pairCodeDisplay.value && pairCodeDisplay.value !== previousCode) {
      logPairAudit('room_code_updated', {
        purpose: pairPurpose.value,
        generation,
        code_display: pairCodeDisplay.value,
        token: pairTokenTail(token.value),
      }, { reportToServer: false })
    }
  } catch {
    logPairAudit('room_code_fetch_error', {
      purpose: pairPurpose.value,
      generation,
    }, { reportToServer: false })
  }
}

function startRoomCodePolling(generation: number) {
  if (roomCodePoll) {
    clearInterval(roomCodePoll)
    roomCodePoll = null
  }
  void fetchRoomCode(generation)
  roomCodePoll = setInterval(() => {
    void fetchRoomCode(generation)
  }, ROOM_CODE_POLL_MS)
}

async function pollStatus() {
  try {
    const res = await authFetch('/api/auth/dingtalk-bind/status', { method: 'GET' })
    const data = (await res.json().catch(() => ({}))) as {
      linked?: boolean
      rate_limited?: boolean
    }
    if (!res.ok) {
      return
    }
    if (data.rate_limited === true) {
      logPairAudit('status_rate_limited', {
        purpose: pairPurpose.value,
        generation: sessionGeneration.value,
      }, { reportToServer: false })
      return
    }
    const linked = data.linked === true
    const done = isUnbind.value ? !linked : linked
    if (done) {
      completed.value = true
      logPairAudit('pairing_completed', {
        purpose: pairPurpose.value,
        generation: sessionGeneration.value,
        linked,
        token: pairTokenTail(token.value),
      })
      notify.success(t(successKey.value))
      emit('completed')
      stopTimers()
    }
  } catch {
    /* keep polling */
  }
}

function startPolling(generation: number) {
  stopTimers()
  logPairAudit('polling_started', {
    purpose: pairPurpose.value,
    generation,
    token: pairTokenTail(token.value),
  }, { reportToServer: false })
  void pollStatus()
  pollTimer = setInterval(() => {
    void pollStatus()
  }, POLL_MS)
  tickTimer = setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
  startRoomCodePolling(generation)
}

async function mintSession() {
  const generation = sessionGeneration.value + 1
  sessionGeneration.value = generation
  tokenLoading.value = true
  completed.value = false
  pairCode.value = ''
  pairCodeDisplay.value = ''
  validUntilUnix.value = 0
  stopTimers()
  logPairAudit('mint_started', {
    purpose: pairPurpose.value,
    generation,
  }, { reportToServer: false })
  try {
    const res = await authFetch(startEndpoint.value, { method: 'POST' })
    const data = (await res.json().catch(() => ({}))) as {
      token?: string
      ttl_seconds?: number
      detail?: { code?: string; message?: string } | string
    }
    if (generation !== sessionGeneration.value) {
      return
    }
    if (!res.ok) {
      const detail = data.detail
      const code =
        typeof detail === 'object' && detail && 'code' in detail ? detail.code : undefined
      logPairAudit('mint_failed', {
        purpose: pairPurpose.value,
        generation,
        reason: code ?? `http_${res.status}`,
      })
      if (code === 'DINGTALK_BIND_NO_ORG') {
        notify.error(t('auth.dingtalkBindNoOrg'))
      } else if (code === 'DINGTALK_BIND_NO_MINDBOT') {
        notify.error(t('auth.dingtalkBindNoMindbot'))
      } else if (code === 'DINGTALK_BIND_NOT_LINKED') {
        notify.error(t('auth.dingtalkUnbindNotLinked'))
      } else if (code === 'DINGTALK_BIND_RATE_LIMIT') {
        notify.warning(t('auth.dingtalkBindPollRateLimited'))
      } else {
        notify.error(t('auth.dingtalkBindMintError'))
      }
      return
    }
    if (!data.token) {
      logPairAudit('mint_failed', {
        purpose: pairPurpose.value,
        generation,
        reason: 'missing_token',
      })
      notify.error(t('auth.dingtalkBindMintError'))
      return
    }
    token.value = data.token
    const ttl = typeof data.ttl_seconds === 'number' ? data.ttl_seconds : BIND_TTL_SECONDS
    expiresAtMs.value = Date.now() + ttl * 1000
    nowMs.value = Date.now()
    logPairAudit('mint_ok', {
      purpose: pairPurpose.value,
      generation,
      token: pairTokenTail(data.token),
      ttl_seconds: ttl,
    })
    startPolling(generation)
  } catch {
    if (generation === sessionGeneration.value) {
      logPairAudit('mint_failed', {
        purpose: pairPurpose.value,
        generation,
        reason: 'network_error',
      })
      notify.error(t('auth.dingtalkBindMintError'))
    }
  } finally {
    if (generation === sessionGeneration.value) {
      tokenLoading.value = false
    }
  }
}

function close() {
  visible.value = false
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      sessionGeneration.value += 1
      completed.value = false
      token.value = ''
      pairCode.value = ''
      pairCodeDisplay.value = ''
      expiresAtMs.value = 0
      validUntilUnix.value = 0
      logPairAudit('modal_open', {
        purpose: pairPurpose.value,
        generation: sessionGeneration.value,
      })
      void mintSession()
    } else {
      sessionGeneration.value += 1
      stopTimers()
      void cancelPendingToken()
      token.value = ''
      pairCode.value = ''
      pairCodeDisplay.value = ''
    }
  }
)

watch(expired, (isExpired) => {
  if (isExpired && token.value && !completed.value) {
    logPairAudit('session_expired', {
      purpose: pairPurpose.value,
      generation: sessionGeneration.value,
      token: pairTokenTail(token.value),
    })
  }
})

onBeforeUnmount(() => {
  sessionGeneration.value += 1
  stopTimers()
})
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="t(titleKey)"
    width="420px"
    align-center
    destroy-on-close
    @close="close"
  >
    <div class="space-y-4 text-sm text-stone-700">
      <p>{{ t(instructionsKey) }}</p>
      <p
        v-if="isUnbind && props.linkedStaffId"
        class="text-stone-500"
      >
        {{ t('auth.dingtalkBindAlreadyLinked', { staff: props.linkedStaffId }) }}
      </p>

      <div class="flex flex-col items-center gap-3 min-h-[240px] justify-center">
        <Loader2
          v-if="tokenLoading"
          class="w-8 h-8 animate-spin text-stone-400"
        />
        <div
          v-else-if="pairCodeDisplay && !completed"
          :key="pairCode"
          class="flex flex-col items-center gap-3 w-full"
        >
          <p
            class="text-4xl font-semibold tracking-[0.2em] tabular-nums text-stone-900"
            aria-live="polite"
          >
            {{ pairCodeDisplay }}
          </p>
          <p class="text-stone-500 text-xs text-center">
            {{ t(codeHintKey) }}
          </p>
          <div
            v-if="pairingActive"
            class="flex items-center gap-2 text-sky-700 text-xs"
          >
            <span class="relative flex h-2 w-2">
              <span
                class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"
              />
              <span class="relative inline-flex rounded-full h-2 w-2 bg-sky-600" />
            </span>
            {{ t(waitingKey) }}
          </div>
        </div>
        <p
          v-if="completed"
          class="text-emerald-600 font-medium"
        >
          {{ t(successKey) }}
        </p>
        <p
          v-else-if="expired"
          class="text-amber-600"
        >
          {{ t(expiredKey) }}
        </p>
        <p
          v-else-if="token && !completed && codeRefreshIn > 0"
          class="text-stone-500 tabular-nums"
        >
          {{ t('auth.dingtalkBindCodeRefreshIn', { s: codeRefreshIn }) }}
        </p>
        <p
          v-else-if="token && !completed"
          class="text-stone-500 tabular-nums"
        >
          {{ t('auth.dingtalkBindCountdown', { s: secondsLeft }) }}
        </p>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <ElButton @click="close">{{ t('common.close') }}</ElButton>
        <ElButton
          v-if="expired && !completed"
          type="primary"
          :loading="tokenLoading"
          @click="mintSession"
        >
          {{ t(regenerateKey) }}
        </ElButton>
      </div>
    </div>
  </ElDialog>
</template>
