<script setup lang="ts">
/**
 * Attendee quick registration after scanning facilitator QR: same shell as LoginModal
 * (light backdrop on /auth, back row, close control).
 */
import { computed, onMounted, ref } from 'vue'

import { ArrowLeft, Loader2, UserPlus } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage, useNotifications } from '@/composables'
import { isTrainingInlineHost } from '@/composables/training/trainingInlineHost'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  quickRegToken: string
  lightBackdrop?: boolean
  persistent?: boolean
}>()

const emit = defineEmits<{
  (e: 'success'): void
  (e: 'cancel'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()

const phone = ref('')
const roomCode = ref('')
const submitting = ref(false)
const tokenProbe = ref<'loading' | 'ok' | 'invalid' | 'rate_limited'>('loading')

function closeModal() {
  emit('cancel')
}

const isVisible = computed({
  get: () => Boolean(props.quickRegToken),
  set: (value: boolean) => {
    if (!value) {
      emit('cancel')
    }
  },
})

/** `/auth`: footer legal link sits below the modal — overlay must not swallow clicks. */
const passThroughFooterClicks = computed(() => Boolean(props.lightBackdrop && props.persistent))
const inlineHost = isTrainingInlineHost()

onMounted(async () => {
  if (!props.quickRegToken) {
    tokenProbe.value = 'invalid'
    return
  }
  try {
    const response = await apiRequest(
      `/api/auth/quick-register/status?channel_token=${encodeURIComponent(props.quickRegToken)}`,
      { method: 'GET' }
    )
    if (response.ok) {
      tokenProbe.value = 'ok'
    } else if (response.status === 429 || response.status === 503) {
      tokenProbe.value = 'rate_limited'
    } else {
      tokenProbe.value = 'invalid'
    }
  } catch {
    tokenProbe.value = 'invalid'
  }
})

async function submitQuickRegister() {
  const phoneDigits = phone.value.replace(/\D/g, '')
  if (phoneDigits.length !== 11) {
    notify.warning(t('auth.modal.phone11Digits'))
    return
  }
  const roomTrimmed = roomCode.value.trim()
  if (roomTrimmed.length !== 6 || !/^\d{6}$/.test(roomTrimmed)) {
    notify.warning(t('auth.quickRegRoomCodeEnter6'))
    return
  }
  if (!props.quickRegToken) {
    notify.error(t('auth.modal.fillRequired'))
    return
  }

  submitting.value = true
  try {
    const response = await apiRequest('/api/auth/register-quick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: phoneDigits,
        room_code: roomTrimmed,
        quick_reg_token: props.quickRegToken,
      }),
    })
    const data = await response.json().catch(() => ({}))
    if (response.ok) {
      let sessionOk = false
      for (let attempt = 0; attempt < 6; attempt++) {
        if (attempt > 0) {
          await new Promise((resolve) => setTimeout(resolve, 100 * attempt))
        }
        sessionOk = await authStore.checkAuth(true)
        if (sessionOk) {
          break
        }
      }
      if (sessionOk) {
        notify.success(t('auth.quickRegRegisterSuccess'))
        emit('success')
      } else {
        notify.warning(t('auth.quickRegSessionUnsure'))
      }
    } else {
      notify.error(
        (typeof (data as { detail?: string }).detail === 'string' &&
          (data as { detail: string }).detail) ||
          t('auth.modal.registerFailed')
      )
    }
  } catch {
    notify.error(t('auth.modal.networkRegisterError'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.register.ribbon')"
    :title="t('swissGlass.hero.register.title')"
    :line1="t('swissGlass.hero.register.line1')"
    :icon="UserPlus"
    :light-backdrop="lightBackdrop"
    :persistent="persistent"
    :teleport-disabled="inlineHost"
    :overlay-class="
      [
        'swiss-glass-card-overlay--auth',
        inlineHost ? 'swiss-glass-card-overlay--contained' : '',
        passThroughFooterClicks ? 'pointer-events-none' : '',
        lightBackdrop ? 'swiss-glass-card-overlay--auth-pad' : '',
      ]
        .filter(Boolean)
        .join(' ')
    "
    :card-class="
      ['swiss-glass-card--auth', passThroughFooterClicks ? 'pointer-events-auto' : '']
        .filter(Boolean)
        .join(' ')
    "
    @close="closeModal"
  >
    <div class="page-header">
      <div class="page-header__row">
        <button
          type="button"
          class="page-header__back"
          @click="closeModal"
        >
          <ArrowLeft
            class="page-header__back-icon"
            aria-hidden="true"
          />
          {{ t('auth.quickRegBackToSignIn') }}
        </button>
      </div>
    </div>

    <form
      class="p-6 space-y-4"
      @submit.prevent="submitQuickRegister"
    >
      <p
        v-if="tokenProbe === 'invalid'"
        class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
        role="status"
      >
        {{ t('auth.quickRegLinkInvalid') }}
      </p>
      <p
        v-else-if="tokenProbe === 'rate_limited'"
        class="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
        role="status"
      >
        {{ t('auth.quickRegProbeRateLimited') }}
      </p>

      <div>
        <label
          class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
          for="auth-qr-phone"
        >
          {{ t('auth.phone') }}
        </label>
        <input
          id="auth-qr-phone"
          v-model="phone"
          type="tel"
          maxlength="11"
          autocomplete="tel"
          class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
          :placeholder="t('auth.modal.phonePlaceholder11')"
        />
      </div>

      <div>
        <label
          class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
          for="auth-qr-room"
        >
          {{ t('auth.quickRegRoomCodeLabel') }}
        </label>
        <input
          id="auth-qr-room"
          v-model="roomCode"
          type="text"
          maxlength="6"
          inputmode="numeric"
          class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all font-mono tracking-wider"
          :placeholder="t('auth.quickRegRoomCodePlaceholder')"
          autocomplete="one-time-code"
        />
        <p class="text-xs text-stone-400 mt-1.5">
          {{ t('auth.quickRegRoomCodeHint') }}
        </p>
      </div>

      <button
        type="submit"
        :disabled="submitting || tokenProbe === 'invalid'"
        class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        <Loader2
          v-if="submitting"
          class="w-4 h-4 animate-spin shrink-0"
        />
        {{ submitting ? t('auth.quickRegSubmitting') : t('auth.quickRegSubmit') }}
      </button>
    </form>
  </SwissGlassCard>
</template>

<style scoped>
.page-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e7e5e4;
}

.page-header__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 22px;
}

.page-header__back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  color: #57534e;
  line-height: 1.25;
}

.page-header__back:hover {
  color: #1c1917;
}

.page-header__back-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
</style>
