<script setup lang="ts">
/**
 * LoginModal - Comprehensive auth modal with login, register, SMS login, and password reset
 *
 * Design: Swiss Design (Modern Minimalism)
 * - Monochromatic stone/neutral palette
 * - Uppercase labels with letter-spacing
 * - Borderless inputs with fill backgrounds
 * - High contrast black/white for primary actions
 * - Generous whitespace, clean geometric shapes
 * - Reference: Linear, Vercel, Stripe aesthetics
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ElPageHeader, ElTabs } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { Eye, EyeOff, Loader2, RefreshCw } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const authStore = useAuthStore()
const { t } = useLanguage()
const notify = useNotifications()

// View states
type ViewState = 'login' | 'register' | 'sms-login' | 'forgot-password'
const currentView = ref<ViewState>('login')
const activeTab = ref<string>('login')

// Login form data
const loginForm = ref({
  phone: '',
  password: '',
  captcha: '',
})

// Register form data
const registerForm = ref({
  phone: '',
  password: '',
  name: '',
  invitationCode: '',
  captcha: '',
})

// SMS Login form data
const smsLoginForm = ref({
  phone: '',
  captcha: '',
  smsCode: '',
})

// Forgot password form data
const forgotForm = ref({
  phone: '',
  captcha: '',
  smsCode: '',
  newPassword: '',
  confirmPassword: '',
})

// Captcha state
const captchaId = ref('')
const captchaImage = ref('')
const captchaLoading = ref(false)

// SMS state
const smsSending = ref(false)
const smsCountdown = ref(0)
const smsCountdownTimer = ref<ReturnType<typeof setInterval> | null>(null)
const smsSent = ref(false)

// Loading states
const isLoading = ref(false)
const showPassword = ref(false)
const showConfirmPassword = ref(false)

// Computed for v-model binding
const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

// Computed for page header title
const pageHeaderTitle = computed(() => {
  return currentView.value === 'sms-login' ? t('auth.smsLogin') : t('auth.resetPassword')
})

// Close modal
function closeModal() {
  // Close the modal
  isVisible.value = false
  resetAllForms()
  currentView.value = 'login'
  activeTab.value = 'login'
  
  // Clear session expired state and pending redirect when modal closes
  if (authStore.showSessionExpiredModal) {
    authStore.closeSessionExpiredModal()
    // Clear pending redirect since user chose to close instead of logging in
    authStore.getAndClearPendingRedirect()
  }
}

// Reset all forms
function resetAllForms() {
  loginForm.value = { phone: '', password: '', captcha: '' }
  registerForm.value = { phone: '', password: '', name: '', invitationCode: '', captcha: '' }
  smsLoginForm.value = { phone: '', captcha: '', smsCode: '' }
  forgotForm.value = { phone: '', captcha: '', smsCode: '', newPassword: '', confirmPassword: '' }
  showPassword.value = false
  showConfirmPassword.value = false
  smsSent.value = false
  smsCountdown.value = 0
  if (smsCountdownTimer.value) {
    clearInterval(smsCountdownTimer.value)
    smsCountdownTimer.value = null
  }
}

// Handle tab change from el-tabs
function handleTabChange(tab: string | number) {
  const tabStr = String(tab)
  activeTab.value = tabStr
  currentView.value = tabStr as ViewState
  refreshCaptcha()
}

// Navigate to sub-views
function showSmsLogin() {
  currentView.value = 'sms-login'
  refreshCaptcha()
}

function showForgotPassword() {
  currentView.value = 'forgot-password'
  refreshCaptcha()
}

function backToLogin() {
  currentView.value = 'login'
  smsSent.value = false
  smsCountdown.value = 0
  if (smsCountdownTimer.value) {
    clearInterval(smsCountdownTimer.value)
    smsCountdownTimer.value = null
  }
  refreshCaptcha()
}

// Fetch captcha image
async function refreshCaptcha() {
  captchaLoading.value = true
  try {
    const result = await authStore.fetchCaptcha()
    if (result) {
      captchaId.value = result.captcha_id
      captchaImage.value = result.captcha_image
    } else {
      notify.error('验证码加载失败')
    }
  } catch (error) {
    console.error('Captcha error:', error)
    notify.error('网络错误，验证码加载失败')
  } finally {
    captchaLoading.value = false
  }
}

// Load captcha when modal opens
watch(
  () => props.visible,
  (newValue) => {
    if (newValue) {
      refreshCaptcha()
      // Prevent body scroll when session expired modal is shown
      if (authStore.showSessionExpiredModal) {
        document.body.style.overflow = 'hidden'
      }
    } else {
      // Restore body scroll when modal closes
      document.body.style.overflow = ''
    }
  }
)

// Also watch for session expired modal state changes
watch(
  () => authStore.showSessionExpiredModal,
  (isSessionExpired) => {
    if (isSessionExpired && props.visible) {
      document.body.style.overflow = 'hidden'
    } else if (!props.visible) {
      document.body.style.overflow = ''
    }
  }
)

// Cleanup: restore body scroll and clear SMS countdown timer on unmount
onBeforeUnmount(() => {
  document.body.style.overflow = ''
  if (smsCountdownTimer.value) {
    clearInterval(smsCountdownTimer.value)
    smsCountdownTimer.value = null
  }
})

// Handle login
async function handleLogin() {
  if (!loginForm.value.phone || !loginForm.value.password) {
    notify.warning('请填写所有字段')
    return
  }

  if (!loginForm.value.captcha || loginForm.value.captcha.length !== 4) {
    notify.warning('请输入4位验证码')
    return
  }

  if (!captchaId.value) {
    notify.warning('请等待验证码加载')
    return
  }

  isLoading.value = true

  try {
    const result = await authStore.login({
      phone: loginForm.value.phone,
      password: loginForm.value.password,
      captcha: loginForm.value.captcha,
      captcha_id: captchaId.value,
    })

    if (result.success) {
      const userName = result.user?.username || ''
      notify.success(userName ? `登录成功，${userName}欢迎你` : '登录成功')

      // If this is a session expired modal, emit success immediately (handler will close modal)
      // Otherwise, close modal normally after delay
      if (authStore.showSessionExpiredModal) {
        emit('success')
      } else {
        setTimeout(() => {
          closeModal()
          emit('success')
        }, 1500)
      }
    } else {
      notify.error(result.message || t('auth.loginFailed'))
      loginForm.value.captcha = ''
      refreshCaptcha()
    }
  } catch (error) {
    console.error('Login error:', error)
    notify.error('网络错误，登录失败')
    loginForm.value.captcha = ''
    refreshCaptcha()
  } finally {
    isLoading.value = false
  }
}

// Handle registration
async function handleRegister() {
  if (
    !registerForm.value.phone ||
    !registerForm.value.password ||
    !registerForm.value.name ||
    !registerForm.value.invitationCode
  ) {
    notify.warning('请填写所有必填项')
    return
  }

  if (registerForm.value.password.length < 8) {
    notify.warning('密码至少需要8个字符')
    return
  }

  if (!registerForm.value.captcha || registerForm.value.captcha.length !== 4) {
    notify.warning('请输入4位验证码')
    return
  }

  isLoading.value = true

  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: registerForm.value.phone,
        password: registerForm.value.password,
        name: registerForm.value.name,
        invitation_code: registerForm.value.invitationCode,
        captcha: registerForm.value.captcha,
        captcha_id: captchaId.value,
      }),
    })

    const data = await response.json()

    if (response.ok) {
      notify.success('注册成功，请登录')
      handleTabChange('login')
      loginForm.value.phone = registerForm.value.phone
    } else {
      notify.error(data.detail || '注册失败')
      registerForm.value.captcha = ''
      refreshCaptcha()
    }
  } catch (error) {
    console.error('Register error:', error)
    notify.error('网络错误，注册失败')
    registerForm.value.captcha = ''
    refreshCaptcha()
  } finally {
    isLoading.value = false
  }
}

// Send SMS code
async function sendSmsCode(type: 'login' | 'reset') {
  const form = type === 'login' ? smsLoginForm.value : forgotForm.value

  if (!form.phone || form.phone.length !== 11) {
    notify.warning('请输入有效的11位手机号')
    return
  }

  if (!form.captcha || form.captcha.length !== 4) {
    notify.warning('请先输入验证码')
    return
  }

  smsSending.value = true

  try {
    const endpoint = type === 'login' ? '/api/auth/sms/send-login' : '/api/auth/sms/send-reset'
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: form.phone,
        captcha: form.captcha,
        captcha_id: captchaId.value,
      }),
    })

    const data = await response.json()

    if (response.ok) {
      notify.success('短信验证码发送成功')
      smsSent.value = true
      startCountdown()
    } else {
      notify.error(data.detail || '短信发送失败')
      form.captcha = ''
      refreshCaptcha()
    }
  } catch (error) {
    console.error('SMS error:', error)
    notify.error('网络错误，短信发送失败')
    form.captcha = ''
    refreshCaptcha()
  } finally {
    smsSending.value = false
  }
}

// Start SMS countdown
function startCountdown() {
  smsCountdown.value = 60
  if (smsCountdownTimer.value) {
    clearInterval(smsCountdownTimer.value)
    smsCountdownTimer.value = null
  }
  smsCountdownTimer.value = setInterval(() => {
    smsCountdown.value--
    if (smsCountdown.value <= 0) {
      if (smsCountdownTimer.value) {
        clearInterval(smsCountdownTimer.value)
        smsCountdownTimer.value = null
      }
    }
  }, 1000)
}

// Handle SMS login
async function handleSmsLogin() {
  if (!smsLoginForm.value.smsCode || smsLoginForm.value.smsCode.length !== 6) {
    notify.warning('请输入6位短信验证码')
    return
  }

  isLoading.value = true

  try {
    const response = await fetch('/api/auth/sms/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: smsLoginForm.value.phone,
        sms_code: smsLoginForm.value.smsCode,
      }),
    })

    const data = await response.json()

    if (response.ok && data.user) {
      authStore.setUser(data.user)
      if (data.token) authStore.setToken(data.token)
      const userName = data.user?.name || ''
      notify.success(userName ? `登录成功，${userName}欢迎你` : '登录成功')

      // If this is a session expired modal, emit success immediately (handler will close modal)
      // Otherwise, close modal normally after delay
      if (authStore.showSessionExpiredModal) {
        emit('success')
      } else {
        setTimeout(() => {
          closeModal()
          emit('success')
        }, 1500)
      }
    } else {
      notify.error(data.detail || '短信登录失败')
    }
  } catch (error) {
    console.error('SMS login error:', error)
    notify.error('网络错误，短信登录失败')
  } finally {
    isLoading.value = false
  }
}

// Handle password reset
async function handleResetPassword() {
  if (!forgotForm.value.smsCode || forgotForm.value.smsCode.length !== 6) {
    notify.warning('请输入6位短信验证码')
    return
  }

  if (!forgotForm.value.newPassword || forgotForm.value.newPassword.length < 8) {
    notify.warning('密码至少需要8个字符')
    return
  }

  if (forgotForm.value.newPassword !== forgotForm.value.confirmPassword) {
    notify.warning('两次输入的密码不一致')
    return
  }

  isLoading.value = true

  try {
    const response = await fetch('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: forgotForm.value.phone,
        sms_code: forgotForm.value.smsCode,
        new_password: forgotForm.value.newPassword,
      }),
    })

    const data = await response.json()

    if (response.ok) {
      notify.success('密码重置成功，请登录')
      backToLogin()
      loginForm.value.phone = forgotForm.value.phone
    } else {
      notify.error(data.detail || '密码重置失败')
    }
  } catch (error) {
    console.error('Reset password error:', error)
    notify.error('网络错误，密码重置失败')
  } finally {
    isLoading.value = false
  }
}

// Handle backdrop click
function handleBackdropClick(event: MouseEvent) {
  if (event.target === event.currentTarget) {
    closeModal()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isVisible"
        class="fixed inset-0 z-1000 flex items-center justify-center p-4"
        :class="{ 'pointer-events-auto': authStore.showSessionExpiredModal }"
        @click="handleBackdropClick"
      >
        <!-- Backdrop -->
        <div
          class="absolute inset-0 bg-stone-900/70"
          :class="{ 'pointer-events-auto': authStore.showSessionExpiredModal }"
        />

        <!-- Modal -->
        <div class="relative w-full max-w-sm">
          <!-- Card -->
          <div class="bg-white rounded-xl shadow-2xl overflow-hidden relative">
            <!-- Close button -->
            <el-button
              class="close-btn"
              :icon="Close"
              circle
              text
              @click="closeModal"
            />
            <!-- Header -->
            <div class="px-8 pt-8 pb-4 text-center border-b border-stone-100">
              <div
                class="w-12 h-12 bg-stone-900 rounded-lg mx-auto mb-4 flex items-center justify-center"
              >
                <span class="text-white font-semibold text-lg tracking-tight">M</span>
              </div>
              <h2 class="text-xl font-semibold text-stone-900 tracking-tight leading-none">
                MindSpring
              </h2>
              <p class="text-xs text-stone-400 tracking-widest uppercase mt-1.5">
                思维教学数智化平台
              </p>
            </div>

            <!-- Tabs (only show for login/register views) -->
            <el-tabs
              v-if="currentView === 'login' || currentView === 'register'"
              v-model="activeTab"
              class="auth-tabs"
              @tab-change="handleTabChange"
            >
              <el-tab-pane
                label="登录"
                name="login"
              />
              <el-tab-pane
                label="注册"
                name="register"
              />
            </el-tabs>

            <!-- Page header for sub-views -->
            <el-page-header
              v-if="currentView === 'sms-login' || currentView === 'forgot-password'"
              class="page-header"
              :title="t('auth.backToLogin')"
              @back="backToLogin"
            >
              <template #content>
                <span class="page-header-title">{{ pageHeaderTitle }}</span>
              </template>
            </el-page-header>

            <!-- Login Form -->
            <form
              v-if="currentView === 'login'"
              class="p-6 space-y-4"
              @submit.prevent="handleLogin"
            >
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  手机号
                </label>
                <input
                  v-model="loginForm.phone"
                  type="tel"
                  placeholder="11位手机号"
                  maxlength="11"
                  autocomplete="username"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  密码
                </label>
                <div class="relative">
                  <input
                    v-model="loginForm.password"
                    :type="showPassword ? 'text' : 'password'"
                    placeholder="请输入密码"
                    autocomplete="current-password"
                    class="w-full px-4 py-3 pr-11 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <button
                    type="button"
                    class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
                    @click="showPassword = !showPassword"
                  >
                    <Eye
                      v-if="showPassword"
                      class="w-4 h-4"
                    />
                    <EyeOff
                      v-else
                      class="w-4 h-4"
                    />
                  </button>
                </div>
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  验证码
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="loginForm.captcha"
                    type="text"
                    placeholder="输入验证码"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    alt="Captcha"
                    class="captcha-image"
                    title="Click to refresh"
                    @click="refreshCaptcha"
                  />
                  <div
                    v-else
                    class="captcha-placeholder"
                    @click="refreshCaptcha"
                  >
                    <Loader2
                      v-if="captchaLoading"
                      class="w-5 h-5 text-stone-400 animate-spin"
                    />
                    <RefreshCw
                      v-else
                      class="w-5 h-5 text-stone-400"
                    />
                  </div>
                </div>
              </div>

              <button
                type="submit"
                :disabled="isLoading"
                class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Loader2
                  v-if="isLoading"
                  class="w-4 h-4 animate-spin"
                />
                {{ isLoading ? '登录中...' : '登录' }}
              </button>

              <!-- Links -->
              <div class="flex justify-center items-center gap-1 pt-2">
                <el-button
                  type="primary"
                  link
                  @click="showForgotPassword"
                >
                  忘记密码
                </el-button>
                <span class="text-stone-300">|</span>
                <el-button
                  type="primary"
                  link
                  @click="showSmsLogin"
                >
                  短信登录
                </el-button>
              </div>
            </form>

            <!-- Register Form -->
            <form
              v-if="currentView === 'register'"
              class="p-6 space-y-4"
              @submit.prevent="handleRegister"
            >
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  手机号 *
                </label>
                <input
                  v-model="registerForm.phone"
                  type="tel"
                  placeholder="11位手机号"
                  maxlength="11"
                  autocomplete="username"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  密码 *
                </label>
                <div class="relative">
                  <input
                    v-model="registerForm.password"
                    :type="showPassword ? 'text' : 'password'"
                    placeholder="至少8位字符"
                    autocomplete="new-password"
                    class="w-full px-4 py-3 pr-11 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <button
                    type="button"
                    class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
                    @click="showPassword = !showPassword"
                  >
                    <Eye
                      v-if="showPassword"
                      class="w-4 h-4"
                    />
                    <EyeOff
                      v-else
                      class="w-4 h-4"
                    />
                  </button>
                </div>
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  姓名 *
                </label>
                <input
                  v-model="registerForm.name"
                  type="text"
                  placeholder="您的姓名"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  邀请码 *
                </label>
                <input
                  v-model="registerForm.invitationCode"
                  type="text"
                  placeholder="学校邀请码"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  验证码 *
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="registerForm.captcha"
                    type="text"
                    placeholder="输入验证码"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    alt="Captcha"
                    class="captcha-image"
                    title="Click to refresh"
                    @click="refreshCaptcha"
                  />
                  <div
                    v-else
                    class="captcha-placeholder"
                    @click="refreshCaptcha"
                  >
                    <Loader2
                      v-if="captchaLoading"
                      class="w-5 h-5 text-stone-400 animate-spin"
                    />
                    <RefreshCw
                      v-else
                      class="w-5 h-5 text-stone-400"
                    />
                  </div>
                </div>
              </div>

              <button
                type="submit"
                :disabled="isLoading"
                class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Loader2
                  v-if="isLoading"
                  class="w-4 h-4 animate-spin"
                />
                {{ isLoading ? '注册中...' : '注册' }}
              </button>
            </form>

            <!-- SMS Login Form -->
            <form
              v-if="currentView === 'sms-login'"
              class="p-6 space-y-4"
              @submit.prevent="handleSmsLogin"
            >
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  手机号
                </label>
                <input
                  v-model="smsLoginForm.phone"
                  type="tel"
                  placeholder="已注册的手机号"
                  maxlength="11"
                  autocomplete="username"
                  :disabled="smsSent"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all disabled:opacity-60"
                />
              </div>

              <div v-if="!smsSent">
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  验证码
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="smsLoginForm.captcha"
                    type="text"
                    placeholder="输入验证码"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    alt="Captcha"
                    class="captcha-image"
                    title="Click to refresh"
                    @click="refreshCaptcha"
                  />
                  <div
                    v-else
                    class="captcha-placeholder"
                    @click="refreshCaptcha"
                  >
                    <Loader2
                      v-if="captchaLoading"
                      class="w-5 h-5 text-stone-400 animate-spin"
                    />
                    <RefreshCw
                      v-else
                      class="w-5 h-5 text-stone-400"
                    />
                  </div>
                </div>
              </div>

              <button
                v-if="!smsSent"
                type="button"
                :disabled="smsSending"
                class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                @click="sendSmsCode('login')"
              >
                <Loader2
                  v-if="smsSending"
                  class="w-4 h-4 animate-spin"
                />
                {{ smsSending ? '发送中...' : '发送短信验证码' }}
              </button>

              <template v-if="smsSent">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    短信验证码
                  </label>
                  <input
                    v-model="smsLoginForm.smsCode"
                    type="text"
                    placeholder="6位短信验证码"
                    maxlength="6"
                    class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <p class="text-xs text-stone-400 mt-1">
                    验证码已发送至
                    {{ smsLoginForm.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') }}
                  </p>
                </div>

                <button
                  type="submit"
                  :disabled="isLoading"
                  class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <Loader2
                    v-if="isLoading"
                    class="w-4 h-4 animate-spin"
                  />
                  {{ isLoading ? '登录中...' : '登录' }}
                </button>

                <div class="text-center">
                  <button
                    type="button"
                    :disabled="smsCountdown > 0"
                    class="text-sm text-stone-500 hover:text-stone-900 transition-colors disabled:opacity-50"
                    @click="sendSmsCode('login')"
                  >
                    {{ smsCountdown > 0 ? `${smsCountdown}秒后重新发送` : '重新发送验证码' }}
                  </button>
                </div>
              </template>
            </form>

            <!-- Forgot Password Form -->
            <form
              v-if="currentView === 'forgot-password'"
              class="p-6 space-y-4"
              @submit.prevent="handleResetPassword"
            >
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  手机号
                </label>
                <input
                  v-model="forgotForm.phone"
                  type="tel"
                  placeholder="已注册的手机号"
                  maxlength="11"
                  autocomplete="username"
                  :disabled="smsSent"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all disabled:opacity-60"
                />
              </div>

              <div v-if="!smsSent">
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  验证码
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="forgotForm.captcha"
                    type="text"
                    placeholder="输入验证码"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    alt="Captcha"
                    class="captcha-image"
                    title="Click to refresh"
                    @click="refreshCaptcha"
                  />
                  <div
                    v-else
                    class="captcha-placeholder"
                    @click="refreshCaptcha"
                  >
                    <Loader2
                      v-if="captchaLoading"
                      class="w-5 h-5 text-stone-400 animate-spin"
                    />
                    <RefreshCw
                      v-else
                      class="w-5 h-5 text-stone-400"
                    />
                  </div>
                </div>
              </div>

              <button
                v-if="!smsSent"
                type="button"
                :disabled="smsSending"
                class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                @click="sendSmsCode('reset')"
              >
                <Loader2
                  v-if="smsSending"
                  class="w-4 h-4 animate-spin"
                />
                {{ smsSending ? '发送中...' : '发送短信验证码' }}
              </button>

              <template v-if="smsSent">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    短信验证码
                  </label>
                  <input
                    v-model="forgotForm.smsCode"
                    type="text"
                    placeholder="6位短信验证码"
                    maxlength="6"
                    class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                </div>

                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    新密码
                  </label>
                  <div class="relative">
                    <input
                      v-model="forgotForm.newPassword"
                      :type="showPassword ? 'text' : 'password'"
                      placeholder="至少8位字符"
                      autocomplete="new-password"
                      class="w-full px-4 py-3 pr-11 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                    />
                    <button
                      type="button"
                      class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
                      @click="showPassword = !showPassword"
                    >
                      <Eye
                        v-if="showPassword"
                        class="w-4 h-4"
                      />
                      <EyeOff
                        v-else
                        class="w-4 h-4"
                      />
                    </button>
                  </div>
                </div>

                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    确认密码
                  </label>
                  <div class="relative">
                    <input
                      v-model="forgotForm.confirmPassword"
                      :type="showConfirmPassword ? 'text' : 'password'"
                      placeholder="再次输入新密码"
                      autocomplete="new-password"
                      class="w-full px-4 py-3 pr-11 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                    />
                    <button
                      type="button"
                      class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
                      @click="showConfirmPassword = !showConfirmPassword"
                    >
                      <Eye
                        v-if="showConfirmPassword"
                        class="w-4 h-4"
                      />
                      <EyeOff
                        v-else
                        class="w-4 h-4"
                      />
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  :disabled="isLoading"
                  class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <Loader2
                    v-if="isLoading"
                    class="w-4 h-4 animate-spin"
                  />
                  {{ isLoading ? '重置中...' : '重置密码' }}
                </button>

                <div class="text-center">
                  <button
                    type="button"
                    :disabled="smsCountdown > 0"
                    class="text-sm text-stone-500 hover:text-stone-900 transition-colors disabled:opacity-50"
                    @click="sendSmsCode('reset')"
                  >
                    {{ smsCountdown > 0 ? `${smsCountdown}秒后重新发送` : '重新发送验证码' }}
                  </button>
                </div>
              </template>
            </form>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal transitions */
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

/* Element Plus Tabs - Swiss Design Override */
.auth-tabs {
  --el-tabs-header-height: 44px;
}

.auth-tabs :deep(.el-tabs__header) {
  margin: 0;
  border-bottom: 1px solid #e7e5e4;
}

.auth-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.auth-tabs :deep(.el-tabs__nav) {
  width: 100%;
  display: flex;
}

.auth-tabs :deep(.el-tabs__item) {
  flex: 1;
  text-align: center;
  padding: 0;
  height: 44px;
  line-height: 44px;
  font-size: 14px;
  font-weight: 500;
  color: #a8a29e;
  transition: color 0.2s;
}

.auth-tabs :deep(.el-tabs__item:hover) {
  color: #78716c;
}

.auth-tabs :deep(.el-tabs__item.is-active) {
  color: #1c1917;
  font-weight: 500;
}

.auth-tabs :deep(.el-tabs__active-bar) {
  background-color: #1c1917;
  height: 2px;
}

.auth-tabs :deep(.el-tabs__content) {
  display: none;
}

/* Element Plus Link Buttons - Swiss Design Override */
.el-button.is-link {
  --el-button-text-color: #78716c;
  --el-button-hover-text-color: #1c1917;
  --el-button-active-text-color: #1c1917;
  font-size: 14px;
  padding: 4px 8px;
}

/* Page header - Swiss Design style */
.page-header {
  padding: 16px 24px;
  border-bottom: 1px solid #e7e5e4;
}

:deep(.el-page-header__left) {
  margin-right: 8px;
}

:deep(.el-page-header__left::after) {
  display: none;
}

:deep(.el-page-header__back) {
  color: #57534e;
  font-size: 14px;
}

:deep(.el-page-header__back:hover) {
  color: #1c1917;
}

.page-header-title {
  font-size: 14px;
  font-weight: 500;
  color: #1c1917;
}

/* Captcha image - sharp display like MindLLMCross */
.captcha-image {
  height: 48px;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.2s ease;
  flex-shrink: 0;
}

.captcha-image:hover {
  opacity: 0.8;
}

.captcha-placeholder {
  height: 48px;
  width: 120px;
  border-radius: 8px;
  cursor: pointer;
  background: #f5f5f4;
  border: 1px solid #e7e5e4;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s ease;
}

.captcha-placeholder:hover {
  opacity: 0.8;
}

/* Close button positioning and styling */
.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}
</style>
