<script setup lang="ts">
/**
 * Attendee quick registration after scanning facilitator QR: same shell as LoginModal
 * (light backdrop on /auth, back row, close control).
 */
import { onMounted, ref } from 'vue'

import { Close } from '@element-plus/icons-vue'
import { ArrowLeft, Loader2 } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
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

function handleBackdropClick() {
  if (props.persistent) {
    return
  }
  closeModal()
}

onMounted(async () => {
  if (!props.quickRegToken) {
    tokenProbe.value = 'invalid'
    return
  }
  try {
    const response = await apiRequest(
      `/api/auth/quick-register/room-code?channel_token=${encodeURIComponent(
        props.quickRegToken
      )}`,
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
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="quickRegToken"
        class="login-modal-overlay fixed inset-0 z-1000 overflow-y-auto overscroll-y-contain"
      >
        <div
          v-if="!lightBackdrop"
          class="absolute inset-0 bg-stone-900/70 pointer-events-none"
        />

        <div
          class="relative min-h-full flex items-center justify-center px-4 pt-4"
          :class="
            lightBackdrop
              ? 'pb-[max(6.5rem,env(safe-area-inset-bottom,0px))] sm:pb-20 md:p-4'
              : 'pb-4'
          "
          @click.self="handleBackdropClick"
        >
          <div class="relative w-full max-w-sm">
            <div class="bg-white rounded-xl shadow-2xl overflow-hidden relative">
              <el-button
                class="close-btn"
                :icon="Close"
                circle
                text
                @click="closeModal"
              />

              <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100">
                <div
                  class="w-12 h-12 bg-stone-900 rounded-lg mx-auto mb-4 flex items-center justify-center"
                >
                  <span class="text-white font-semibold text-lg tracking-tight">M</span>
                </div>
                <h2 class="text-xl font-semibold text-stone-900 tracking-tight leading-none">
                  {{ t('auth.modal.productTitle') }}
                </h2>
                <p class="text-xs text-stone-400 tracking-wide mt-1.5">
                  {{ t('auth.modal.tagline') }}
                </p>
              </div>

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
                  <span class="page-header-title">
                    {{ t('auth.quickRegPageTitle') }}
                  </span>
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
                  {{
                    submitting
                      ? t('auth.quickRegSubmitting')
                      : t('auth.quickRegSubmit')
                  }}
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.login-modal-overlay {
  -webkit-overflow-scrolling: touch;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: transform 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95);
}

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

.page-header-title {
  font-size: 14px;
  font-weight: 500;
  color: #1c1917;
  flex-shrink: 0;
}

.close-btn {
  position: absolute;
  top: 12px;
  inset-inline-end: 12px;
  z-index: 10;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}
</style>
