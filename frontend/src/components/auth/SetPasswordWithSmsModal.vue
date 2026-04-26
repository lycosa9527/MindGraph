<script setup lang="ts">
/**
 * Set login password with SMS (reset_password code) while logged in — no session revoke.
 */
import { computed, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()

const isVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const newPassword = ref('')
const confirmPassword = ref('')
const captcha = ref('')
const captchaId = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)
const smsCode = ref('')
const smsSending = ref(false)
const smsCountdown = ref(0)
const submitting = ref(false)

let smsTimer: ReturnType<typeof setInterval> | null = null

const boundPhone = computed(() => (authStore.user?.phone || '').trim())

function startCountdown() {
  smsCountdown.value = 60
  if (smsTimer) {
    clearInterval(smsTimer)
    smsTimer = null
  }
  smsTimer = setInterval(() => {
    smsCountdown.value--
    if (smsCountdown.value <= 0 && smsTimer) {
      clearInterval(smsTimer)
      smsTimer = null
    }
  }, 1000)
}

function close() {
  isVisible.value = false
}

async function loadCaptcha() {
  captchaLoading.value = true
  try {
    const res = await authStore.fetchCaptcha()
    if (res) {
      captchaId.value = res.captcha_id
      captchaImage.value = res.captcha_image
    } else {
      notify.error(t('auth.modal.captchaLoadFailed'))
    }
  } catch {
    notify.error(t('auth.modal.captchaNetworkError'))
  } finally {
    captchaLoading.value = false
  }
}

async function sendResetSms() {
  if (!boundPhone.value || boundPhone.value.length !== 11) {
    notify.warning(t('auth.modal.phone11Digits'))
    return
  }
  if (!captcha.value || captcha.value.length !== 4) {
    notify.warning(t('auth.modal.enterCaptchaFirst'))
    return
  }
  if (!captchaId.value) {
    notify.warning(t('auth.modal.waitCaptchaLoad'))
    return
  }
  if (smsCountdown.value > 0) {
    return
  }

  smsSending.value = true
  try {
    const response = await fetch('/api/auth/sms/send-reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        phone: boundPhone.value,
        captcha: captcha.value,
        captcha_id: captchaId.value,
      }),
    })
    const data = await response.json().catch(() => ({}))
    if (response.ok) {
      notify.success(t('auth.modal.smsSentSuccess'))
      startCountdown()
    } else {
      notify.error(
        (typeof data.detail === 'string' && data.detail) || t('auth.modal.smsSendFailed')
      )
      captcha.value = ''
      void loadCaptcha()
    }
  } catch {
    notify.error(t('auth.modal.networkSmsError'))
    captcha.value = ''
    void loadCaptcha()
  } finally {
    smsSending.value = false
  }
}

async function submit() {
  if (newPassword.value.length < 8) {
    notify.warning(t('auth.modal.passwordMin8'))
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    notify.warning(t('auth.modal.passwordMismatch'))
    return
  }
  if (!smsCode.value || smsCode.value.length !== 6) {
    notify.warning(t('auth.modal.enter6DigitSms'))
    return
  }

  submitting.value = true
  try {
    const response = await apiRequest('/api/auth/set-password-with-sms', {
      method: 'POST',
      body: JSON.stringify({
        new_password: newPassword.value,
        sms_code: smsCode.value,
      }),
    })
    const data = await response.json().catch(() => ({}))
    if (response.ok) {
      notify.success(
        (typeof (data as { message?: string }).message === 'string' &&
          (data as { message: string }).message) ||
          t('auth.passwordChangeSuccess')
      )
      await authStore.checkAuth()
      emit('success')
      close()
      newPassword.value = ''
      confirmPassword.value = ''
      smsCode.value = ''
    } else {
      notify.error(
        (typeof (data as { detail?: string }).detail === 'string' &&
          (data as { detail: string }).detail) ||
          t('auth.passwordChangeFailed')
      )
    }
  } catch {
    notify.error(t('auth.passwordChangeFailed'))
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      newPassword.value = ''
      confirmPassword.value = ''
      smsCode.value = ''
      captcha.value = ''
      void loadCaptcha()
    }
  }
)
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-[60] flex items-center justify-center p-4"
        @click.self="close"
      >
        <div class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]" />
        <div class="relative w-full max-w-md bg-white rounded-xl shadow-2xl p-6">
          <h2 class="text-lg font-semibold text-stone-900 mb-1">
            {{ t('auth.setPasswordWithSmsTitle') }}
          </h2>
          <p class="text-sm text-stone-500 mb-4">
            {{ t('auth.setPasswordWithSmsHint') }}
          </p>
          <p
            v-if="boundPhone"
            class="text-sm text-stone-600 mb-4"
          >
            {{ t('auth.phone') }}: {{ boundPhone }}
          </p>
          <div class="space-y-3">
            <div>
              <label
                class="block text-xs text-stone-500 mb-1"
                for="sp-captcha"
              >
                {{ t('auth.captcha') }}
              </label>
              <div class="flex gap-2">
                <input
                  id="sp-captcha"
                  v-model="captcha"
                  type="text"
                  maxlength="4"
                  class="min-w-0 flex-1 px-3 py-2 border border-stone-200 rounded-lg"
                />
                <button
                  type="button"
                  class="w-28 border border-stone-200 rounded-lg overflow-hidden"
                  @click="loadCaptcha"
                >
                  <img
                    v-if="captchaImage"
                    :src="captchaImage"
                    class="h-9 w-full object-cover"
                    alt=""
                  />
                </button>
              </div>
            </div>
            <ElButton
              type="primary"
              :loading="smsSending"
              :disabled="smsCountdown > 0"
              @click="sendResetSms"
            >
              {{
                smsCountdown > 0
                  ? t('auth.modal.resendIn', { seconds: smsCountdown })
                  : t('auth.modal.sendSmsCode')
              }}
            </ElButton>
            <div>
              <label
                class="block text-xs text-stone-500 mb-1"
                for="sp-sms"
              >
                {{ t('auth.modal.smsCodeLabel') }}
              </label>
              <input
                id="sp-sms"
                v-model="smsCode"
                type="text"
                maxlength="6"
                class="w-full px-3 py-2 border border-stone-200 rounded-lg"
              />
            </div>
            <div>
              <label
                class="block text-xs text-stone-500 mb-1"
                for="sp-np"
              >
                {{ t('auth.modal.newPassword') }}
              </label>
              <input
                id="sp-np"
                v-model="newPassword"
                type="password"
                autocomplete="new-password"
                class="w-full px-3 py-2 border border-stone-200 rounded-lg"
              />
            </div>
            <div>
              <label
                class="block text-xs text-stone-500 mb-1"
                for="sp-cp"
              >
                {{ t('auth.modal.confirmPassword') }}
              </label>
              <input
                id="sp-cp"
                v-model="confirmPassword"
                type="password"
                autocomplete="new-password"
                class="w-full px-3 py-2 border border-stone-200 rounded-lg"
              />
            </div>
            <div class="flex justify-end gap-2 pt-2">
              <ElButton @click="close">
                {{ t('common.cancel') }}
              </ElButton>
              <ElButton
                type="primary"
                :loading="submitting"
                @click="submit"
              >
                {{
                  submitting
                    ? t('auth.setPasswordWithSmsSubmitting')
                    : t('auth.setPasswordWithSmsSubmit')
                }}
              </ElButton>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
