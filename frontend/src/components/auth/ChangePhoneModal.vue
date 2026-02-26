<script setup lang="ts">
/**
 * ChangePhoneModal - Modal for changing user phone number with SMS verification
 *
 * Design: Swiss Design (Modern Minimalism) with dark grey/black theme
 *
 * Flow:
 * 1. User enters new phone number
 * 2. User enters captcha and clicks "Send Code"
 * 3. User enters SMS verification code
 * 4. Phone number is updated
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ElButton, ElInput } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

const notify = useNotifications()

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

// Form state
const newPhone = ref('')
const captchaCode = ref('')
const smsCode = ref('')

// Captcha state
const captchaId = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)

// SMS state
const smsSent = ref(false)
const smsLoading = ref(false)
const countdown = ref(0)
let countdownTimer: number | null = null

// Submit state
const submitting = ref(false)

// Validation
const phoneError = ref('')
const captchaError = ref('')
const smsError = ref('')

// Reset form when modal opens
watch(isVisible, async (val) => {
  if (val) {
    resetForm()
    await fetchCaptcha()
  }
})

function resetForm() {
  newPhone.value = ''
  captchaCode.value = ''
  smsCode.value = ''
  captchaId.value = ''
  captchaImage.value = ''
  smsSent.value = false
  countdown.value = 0
  phoneError.value = ''
  captchaError.value = ''
  smsError.value = ''
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function closeModal() {
  isVisible.value = false
}

onBeforeUnmount(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
})

async function fetchCaptcha() {
  captchaLoading.value = true
  captchaError.value = ''
  try {
    const response = await fetch('/api/auth/captcha/generate', {
      credentials: 'same-origin',
    })
    if (response.ok) {
      const data = await response.json()
      captchaId.value = data.captcha_id
      captchaImage.value = data.captcha_image
    } else {
      captchaError.value = '获取验证码失败，请刷新重试'
    }
  } catch {
    captchaError.value = '网络错误，请刷新重试'
  } finally {
    captchaLoading.value = false
  }
}

function validatePhone(): boolean {
  phoneError.value = ''
  if (!newPhone.value) {
    phoneError.value = '请输入新手机号'
    return false
  }
  if (!/^1\d{10}$/.test(newPhone.value)) {
    phoneError.value = '请输入有效的11位手机号'
    return false
  }
  // Check if same as current phone
  const currentPhone = authStore.user?.phone || ''
  if (newPhone.value === currentPhone) {
    phoneError.value = '新手机号与当前手机号相同'
    return false
  }
  return true
}

function validateCaptcha(): boolean {
  captchaError.value = ''
  if (!captchaCode.value) {
    captchaError.value = '请输入图形验证码'
    return false
  }
  if (captchaCode.value.length !== 4) {
    captchaError.value = '请输入4位验证码'
    return false
  }
  return true
}

function validateSmsCode(): boolean {
  smsError.value = ''
  if (!smsCode.value) {
    smsError.value = '请输入短信验证码'
    return false
  }
  if (!/^\d{6}$/.test(smsCode.value)) {
    smsError.value = '请输入6位数字验证码'
    return false
  }
  return true
}

async function sendSmsCode() {
  if (!validatePhone() || !validateCaptcha()) {
    return
  }

  smsLoading.value = true
  smsError.value = ''

  try {
    // Use credentials (token in httpOnly cookie)
    const response = await fetch('/api/auth/phone/send-code', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_phone: newPhone.value,
        captcha: captchaCode.value,
        captcha_id: captchaId.value,
      }),
    })

    const data = await response.json()

    if (response.ok) {
      smsSent.value = true
      notify.success('验证码发送成功')
      startCountdown(data.resend_after || 60)
    } else {
      // Handle specific errors
      const errorMsg = data.detail || '发送验证码失败'
      if (errorMsg.includes('验证码')) {
        captchaError.value = errorMsg
        await fetchCaptcha()
        captchaCode.value = ''
      } else if (errorMsg.includes('手机号')) {
        phoneError.value = errorMsg
      } else {
        notify.error(errorMsg)
      }
    }
  } catch {
    notify.error('网络错误，请重试')
  } finally {
    smsLoading.value = false
  }
}

function startCountdown(seconds: number) {
  countdown.value = seconds
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }
  countdownTimer = window.setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      if (countdownTimer) {
        clearInterval(countdownTimer)
        countdownTimer = null
      }
    }
  }, 1000)
}

async function handleSubmit() {
  if (!validatePhone() || !validateSmsCode()) {
    return
  }

  submitting.value = true

  try {
    // Use credentials (token in httpOnly cookie)
    const response = await fetch('/api/auth/phone/change', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_phone: newPhone.value,
        sms_code: smsCode.value,
      }),
    })

    const data = await response.json()

    if (response.ok) {
      notify.success('手机号更换成功')
      emit('success')
      closeModal()
    } else {
      const errorMsg = data.detail || '更换手机号失败'
      if (errorMsg.includes('验证码')) {
        smsError.value = errorMsg
      } else if (errorMsg.includes('手机号')) {
        phoneError.value = errorMsg
      } else {
        notify.error(errorMsg)
      }
    }
  } catch {
    notify.error('网络错误，请重试')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @click.self="closeModal"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-stone-900/60 backdrop-blur-[2px]" />

        <!-- Modal -->
        <div class="relative w-full max-w-md">
          <!-- Card -->
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden">
            <!-- Header -->
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100 relative">
              <el-button
                :icon="Close"
                circle
                text
                class="close-btn"
                @click="closeModal"
              />
              <h2 class="text-lg font-semibold text-stone-900 tracking-tight">更换手机号</h2>
              <p class="text-sm text-stone-500 mt-1">验证新手机号后完成更换</p>
            </div>

            <!-- Content -->
            <div class="p-8 space-y-5">
              <!-- New Phone Input -->
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  新手机号
                </label>
                <el-input
                  v-model="newPhone"
                  placeholder="请输入新的11位手机号"
                  maxlength="11"
                  :disabled="smsSent"
                  class="phone-input"
                  @input="phoneError = ''"
                />
                <p
                  v-if="phoneError"
                  class="text-xs text-red-500 mt-1"
                >
                  {{ phoneError }}
                </p>
              </div>

              <!-- Captcha Row (only show before SMS sent) -->
              <div v-if="!smsSent">
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  图形验证码
                </label>
                <div class="flex gap-3">
                  <el-input
                    v-model="captchaCode"
                    placeholder="请输入验证码"
                    maxlength="4"
                    class="flex-1 captcha-input"
                    @input="captchaError = ''"
                    @keyup.enter="sendSmsCode"
                  />
                  <img
                    v-if="captchaImage"
                    :src="captchaImage"
                    alt="验证码"
                    class="h-10 rounded cursor-pointer border border-stone-200 hover:border-stone-400 transition-colors"
                    :class="{ 'opacity-50': captchaLoading }"
                    @click="fetchCaptcha"
                  />
                </div>
                <p
                  v-if="captchaError"
                  class="text-xs text-red-500 mt-1"
                >
                  {{ captchaError }}
                </p>
              </div>

              <!-- SMS Code Input (after SMS sent) -->
              <div v-if="smsSent">
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  短信验证码
                </label>
                <div class="flex gap-3">
                  <el-input
                    v-model="smsCode"
                    placeholder="请输入6位验证码"
                    maxlength="6"
                    class="flex-1 sms-input"
                    @input="smsError = ''"
                    @keyup.enter="handleSubmit"
                  />
                  <button
                    class="px-4 py-2 bg-stone-200 text-stone-700 font-medium rounded-lg hover:bg-stone-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                    :disabled="countdown > 0 || smsLoading"
                    @click="sendSmsCode"
                  >
                    {{ countdown > 0 ? `${countdown}s` : '重新发送' }}
                  </button>
                </div>
                <p
                  v-if="smsError"
                  class="text-xs text-red-500 mt-1"
                >
                  {{ smsError }}
                </p>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-8 pb-8 flex gap-3">
              <button
                class="flex-1 py-3 bg-stone-100 text-stone-700 font-medium rounded-lg hover:bg-stone-200 active:bg-stone-300 transition-all"
                @click="closeModal"
              >
                取消
              </button>
              <!-- Send SMS Button (before SMS sent) -->
              <button
                v-if="!smsSent"
                class="flex-1 py-3 bg-stone-800 text-white font-medium rounded-lg hover:bg-stone-700 active:bg-stone-900 focus:ring-2 focus:ring-stone-800 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="smsLoading"
                @click="sendSmsCode"
              >
                {{ smsLoading ? '发送中...' : '发送验证码' }}
              </button>
              <!-- Confirm Button (after SMS sent) -->
              <button
                v-if="smsSent"
                class="flex-1 py-3 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="submitting"
                @click="handleSubmit"
              >
                {{ submitting ? '提交中...' : '确认更换' }}
              </button>
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

/* Close button positioning and styling */
.close-btn {
  position: absolute;
  top: 16px;
  right: 16px;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}

/* Input styling - Swiss design with dark grey theme */
.phone-input :deep(.el-input__wrapper),
.captcha-input :deep(.el-input__wrapper),
.sms-input :deep(.el-input__wrapper) {
  border-radius: 8px;
  padding: 8px 14px;
  box-shadow: none;
  border: 1px solid #d6d3d1;
  transition: all 0.2s;
}

.phone-input :deep(.el-input__wrapper:hover),
.captcha-input :deep(.el-input__wrapper:hover),
.sms-input :deep(.el-input__wrapper:hover) {
  border-color: #a8a29e;
}

.phone-input :deep(.el-input__wrapper.is-focus),
.captcha-input :deep(.el-input__wrapper.is-focus),
.sms-input :deep(.el-input__wrapper.is-focus) {
  border-color: #44403c;
  box-shadow: 0 0 0 2px rgba(68, 64, 60, 0.1);
}

.phone-input :deep(.el-input__inner),
.captcha-input :deep(.el-input__inner),
.sms-input :deep(.el-input__inner) {
  color: #1c1917;
}

.phone-input :deep(.el-input__inner::placeholder),
.captcha-input :deep(.el-input__inner::placeholder),
.sms-input :deep(.el-input__inner::placeholder) {
  color: #a8a29e;
}
</style>
