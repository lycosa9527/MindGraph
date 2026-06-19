<script setup lang="ts">
/**
 * DingTalk account bind modal — mint QR, poll status, revoke on close.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ElButton, ElDialog } from 'element-plus'

import { Loader2 } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { usePublicSiteUrl } from '@/composables/core/usePublicSiteUrl'
import { authFetch } from '@/utils/api'

const BIND_TTL_SECONDS = 600
const POLL_MS = 2500
const QR_CODE_POLL_MS = 5000

const props = defineProps<{ modelValue: boolean; linkedStaffId?: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; linked: [] }>()

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const token = ref('')
const bindCode = ref('')
const qrQuery = ref('')
const tokenLoading = ref(false)
const expiresAtMs = ref(0)
const validUntilUnix = ref(0)
const periodSeconds = ref(30)
const nowMs = ref(Date.now())
const linked = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let tickTimer: ReturnType<typeof setInterval> | null = null
let qrCodePoll: ReturnType<typeof setInterval> | null = null

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const bindUrl = computed(() => {
  if (!publicSiteUrl.value) {
    return ''
  }
  const query = qrQuery.value
  if (query) {
    return `${publicSiteUrl.value}/bind/dingtalk?${query}`
  }
  if (!token.value || !bindCode.value) {
    return ''
  }
  return `${publicSiteUrl.value}/bind/dingtalk?t=${encodeURIComponent(token.value)}&c=${encodeURIComponent(bindCode.value)}`
})

const qrSrc = computed(() => {
  const u = bindUrl.value
  if (!u) {
    return ''
  }
  return `/api/qrcode?data=${encodeURIComponent(u)}&size=260`
})

const secondsLeft = computed(() => {
  if (!expiresAtMs.value) {
    return 0
  }
  return Math.max(0, Math.ceil((expiresAtMs.value - nowMs.value) / 1000))
})

const qrRefreshIn = computed(() => {
  if (!validUntilUnix.value) {
    return 0
  }
  return Math.max(0, Math.ceil(validUntilUnix.value - nowMs.value / 1000))
})

const expired = computed(() => secondsLeft.value <= 0 && !!token.value && !linked.value)

function stopTimers() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (tickTimer) {
    clearInterval(tickTimer)
    tickTimer = null
  }
  if (qrCodePoll) {
    clearInterval(qrCodePoll)
    qrCodePoll = null
  }
}

async function cancelPendingToken() {
  try {
    await authFetch('/api/auth/dingtalk-bind/cancel', { method: 'POST' })
  } catch {
    /* best effort */
  }
}

async function fetchQrCode() {
  if (!token.value) {
    return
  }
  try {
    const res = await authFetch(
      `/api/auth/dingtalk-bind/qr-code?bind_token=${encodeURIComponent(token.value)}`,
      { method: 'GET' }
    )
    const data = (await res.json().catch(() => ({}))) as {
      code?: string
      qr_query?: string
      valid_until_unix?: number
      period_seconds?: number
    }
    if (!res.ok) {
      return
    }
    if (typeof data.code === 'string') {
      bindCode.value = data.code
    }
    if (typeof data.qr_query === 'string') {
      qrQuery.value = data.qr_query
    }
    if (typeof data.valid_until_unix === 'number') {
      validUntilUnix.value = data.valid_until_unix
    }
    if (typeof data.period_seconds === 'number' && data.period_seconds > 0) {
      periodSeconds.value = data.period_seconds
    }
  } catch {
    /* keep last QR payload */
  }
}

function startQrCodePolling() {
  if (qrCodePoll) {
    clearInterval(qrCodePoll)
    qrCodePoll = null
  }
  void fetchQrCode()
  qrCodePoll = setInterval(() => {
    void fetchQrCode()
  }, QR_CODE_POLL_MS)
}

async function pollStatus() {
  try {
    const res = await authFetch('/api/auth/dingtalk-bind/status', { method: 'GET' })
    const data = (await res.json().catch(() => ({}))) as {
      linked?: boolean
      detail?: { code?: string; message?: string } | string
    }
    if (res.status === 429) {
      notify.warning(t('auth.dingtalkBindPollRateLimited'))
      return
    }
    if (!res.ok) {
      return
    }
    if (data.linked) {
      linked.value = true
      notify.success(t('auth.dingtalkBindSuccess'))
      emit('linked')
      stopTimers()
    }
  } catch {
    /* keep polling */
  }
}

function startPolling() {
  stopTimers()
  pollTimer = setInterval(() => {
    void pollStatus()
  }, POLL_MS)
  tickTimer = setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
  startQrCodePolling()
}

async function mintToken() {
  tokenLoading.value = true
  linked.value = false
  bindCode.value = ''
  qrQuery.value = ''
  validUntilUnix.value = 0
  try {
    const res = await authFetch('/api/auth/dingtalk-bind/start', { method: 'POST' })
    const data = (await res.json().catch(() => ({}))) as {
      token?: string
      ttl_seconds?: number
      detail?: { code?: string; message?: string } | string
    }
    if (!res.ok) {
      const detail = data.detail
      const code =
        typeof detail === 'object' && detail && 'code' in detail ? detail.code : undefined
      if (code === 'DINGTALK_BIND_NO_ORG') {
        notify.error(t('auth.dingtalkBindNoOrg'))
      } else if (code === 'DINGTALK_BIND_NO_MINDBOT') {
        notify.error(t('auth.dingtalkBindNoMindbot'))
      } else if (code === 'DINGTALK_BIND_RATE_LIMIT') {
        notify.warning(t('auth.dingtalkBindPollRateLimited'))
      } else {
        notify.error(t('auth.dingtalkBindMintError'))
      }
      return
    }
    if (!data.token) {
      notify.error(t('auth.dingtalkBindMintError'))
      return
    }
    token.value = data.token
    const ttl = typeof data.ttl_seconds === 'number' ? data.ttl_seconds : BIND_TTL_SECONDS
    expiresAtMs.value = Date.now() + ttl * 1000
    nowMs.value = Date.now()
    startPolling()
  } catch {
    notify.error(t('auth.dingtalkBindMintError'))
  } finally {
    tokenLoading.value = false
  }
}

function close() {
  visible.value = false
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      linked.value = false
      token.value = ''
      bindCode.value = ''
      qrQuery.value = ''
      expiresAtMs.value = 0
      validUntilUnix.value = 0
      void mintToken()
    } else {
      stopTimers()
      void cancelPendingToken()
      token.value = ''
      bindCode.value = ''
      qrQuery.value = ''
    }
  }
)

onBeforeUnmount(() => {
  stopTimers()
})
</script>

<template>
  <ElDialog
    v-model="visible"
    :title="t('auth.dingtalkBindTitle')"
    width="420px"
    align-center
    destroy-on-close
    @close="close"
  >
    <div class="space-y-4 text-sm text-stone-700">
      <p>{{ t('auth.dingtalkBindInstructions') }}</p>
      <p
        v-if="props.linkedStaffId"
        class="text-stone-500"
      >
        {{ t('auth.dingtalkBindAlreadyLinked', { staff: props.linkedStaffId }) }}
      </p>

      <div class="flex flex-col items-center gap-3 min-h-[280px] justify-center">
        <Loader2
          v-if="tokenLoading"
          class="w-8 h-8 animate-spin text-stone-400"
        />
        <img
          v-else-if="qrSrc && !linked"
          :key="qrQuery"
          :src="qrSrc"
          :alt="t('auth.dingtalkBindQrAlt')"
          class="w-[260px] h-[260px] rounded-lg border border-stone-200"
        />
        <p
          v-if="linked"
          class="text-emerald-600 font-medium"
        >
          {{ t('auth.dingtalkBindSuccess') }}
        </p>
        <p
          v-else-if="expired"
          class="text-amber-600"
        >
          {{ t('auth.dingtalkBindExpiredHint') }}
        </p>
        <p
          v-else-if="token && !linked && qrRefreshIn > 0"
          class="text-stone-500 tabular-nums"
        >
          {{ t('auth.dingtalkBindQrRefreshIn', { s: qrRefreshIn }) }}
        </p>
        <p
          v-else-if="token && !linked"
          class="text-stone-500 tabular-nums"
        >
          {{ t('auth.dingtalkBindCountdown', { s: secondsLeft }) }}
        </p>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <ElButton @click="close">{{ t('common.close') }}</ElButton>
        <ElButton
          v-if="expired && !linked"
          type="primary"
          :loading="tokenLoading"
          @click="mintToken"
        >
          {{ t('auth.dingtalkBindRegenerate') }}
        </ElButton>
      </div>
    </div>
  </ElDialog>
</template>
