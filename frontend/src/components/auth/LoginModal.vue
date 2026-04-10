<script setup lang="ts">
/**
 * LoginModal - Auth modal: password login, register (phone or overseas email), OTP login
 * (SMS code or email verification code), and password reset (SMS or email code).
 *
 * Design: Swiss Design (Modern Minimalism)
 * - Monochromatic stone/neutral palette
 * - Small-caps-style letter-spacing on labels (no forced uppercase)
 * - Borderless inputs with fill backgrounds
 * - High contrast black/white for primary actions
 * - Generous whitespace, clean geometric shapes
 * - Reference: Linear, Vercel, Stripe aesthetics
 */
import { computed, nextTick, ref } from 'vue'

import { Close } from '@element-plus/icons-vue'

import { ArrowLeft, Eye, EyeOff, Loader2, RefreshCw } from 'lucide-vue-next'

import { useLoginModal } from '@/composables/auth/useLoginModal'

const props = defineProps<{
  visible: boolean
  /**
   * `/auth`: no full-screen scrim — page background stays fully visible.
   * Default uses a dark scrim (`stone-900/70`) for session-expired and other overlays.
   */
  lightBackdrop?: boolean
  /**
   * When true, clicking outside the modal does nothing (no backdrop dismiss).
   * Use on dedicated auth pages where dismissing the modal has no sensible fallback.
   */
  persistent?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const {
  authStore,
  t,
  currentView,
  activeTab,
  loginForm,
  registerForm,
  smsLoginForm,
  forgotForm,
  captchaImage,
  captchaLoading,
  smsSending,
  smsCountdown,
  smsSent,
  isLoading,
  showPassword,
  showConfirmPassword,
  isVisible,
  pageHeaderTitle,
  closeModal,
  switchLoginRegisterTab,
  showSmsLogin,
  showForgotPassword,
  backToLogin,
  refreshCaptcha,
  handleLogin,
  handleRegister,
  sendRegisterEmailCode,
  sendSmsCode,
  handleSmsLogin,
  registerPath,
  setRegisterPath,
  isBothRegister,
  showOverseasEmailFlow,
  showMainlandPhoneFlow,
  registerRegion,
  registerRegionLoading,
  forgotUsesEmail,
  smsLoginUsesEmail,
  maskIdentifierForCodeSent,
  overseasAcknowledgeCheckboxLabel,
  emailSending,
  emailCountdown,
  handleResetPassword,
  handleBackdropClick,
} = useLoginModal(props, emit)

const registrationEmailHint = computed(() => t('auth.modal.registrationEmailHint').trim())

/** Focus account field for email + password sign-in on the same form. */
const loginIdentifierRef = ref<HTMLInputElement | null>(null)

function focusSesLogin() {
  void nextTick(() => {
    loginIdentifierRef.value?.focus()
  })
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
        <!-- Full-screen scrim (skipped on /auth so the route background shows through) -->
        <div
          v-if="!lightBackdrop"
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
                {{ t('auth.modal.productTitle') }}
              </h2>
              <p class="text-xs text-stone-400 tracking-wide mt-1.5">
                {{ t('auth.modal.tagline') }}
              </p>
            </div>

            <!-- Login / Register switch (custom; Element Plus tabs use scroll/transform and mis-align in narrow modals) -->
            <div
              v-if="currentView === 'login' || currentView === 'register'"
              class="auth-tab-switch"
              role="tablist"
              :aria-label="t('auth.loginRegister')"
            >
              <button
                type="button"
                role="tab"
                :aria-selected="activeTab === 'login'"
                class="auth-tab-switch__btn"
                :class="{ 'auth-tab-switch__btn--active': activeTab === 'login' }"
                @click="switchLoginRegisterTab('login')"
              >
                {{ t('auth.login') }}
              </button>
              <button
                type="button"
                role="tab"
                :aria-selected="activeTab === 'register'"
                class="auth-tab-switch__btn"
                :class="{ 'auth-tab-switch__btn--active': activeTab === 'register' }"
                @click="switchLoginRegisterTab('register')"
              >
                {{ t('auth.register') }}
              </button>
            </div>

            <!-- Sub-view header: back control is icon + label on one line (not el-page-header — it stacks title). -->
            <div
              v-if="currentView === 'sms-login' || currentView === 'forgot-password'"
              class="page-header"
            >
              <div class="page-header__row">
                <button
                  type="button"
                  class="page-header__back"
                  @click="backToLogin"
                >
                  <ArrowLeft
                    class="page-header__back-icon"
                    aria-hidden="true"
                  />
                  {{ t('auth.backToLogin') }}
                </button>
                <span
                  v-if="currentView === 'sms-login'"
                  class="page-header-title"
                >
                  {{ pageHeaderTitle }}
                </span>
              </div>
            </div>

            <!-- Login Form -->
            <form
              v-if="currentView === 'login'"
              class="p-6 space-y-4"
              @submit.prevent="handleLogin"
            >
              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="login-phone"
                >
                  {{ t('auth.loginPhoneOrEmail') }}
                </label>
                <input
                  id="login-phone"
                  ref="loginIdentifierRef"
                  v-model="loginForm.phone"
                  type="text"
                  name="login-phone"
                  :placeholder="t('auth.modal.phonePlaceholder11')"
                  maxlength="254"
                  autocomplete="username"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="login-password"
                >
                  {{ t('auth.password') }}
                </label>
                <div class="relative">
                  <input
                    id="login-password"
                    v-model="loginForm.password"
                    :type="showPassword ? 'text' : 'password'"
                    name="login-password"
                    :placeholder="t('auth.modal.passwordPlaceholder')"
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
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="login-captcha"
                >
                  {{ t('auth.captcha') }}
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    id="login-captcha"
                    v-model="loginForm.captcha"
                    type="text"
                    name="login-captcha"
                    :placeholder="t('auth.modal.captchaPlaceholderShort')"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    :alt="t('auth.captcha')"
                    class="captcha-image"
                    :title="t('auth.clickToRefresh')"
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
                {{ isLoading ? t('auth.modal.loggingIn') : t('auth.login') }}
              </button>

              <!-- Links -->
              <div
                class="flex flex-wrap justify-center items-center gap-x-1 gap-y-1 pt-2 text-sm"
              >
                <el-button
                  type="primary"
                  link
                  @click="showForgotPassword"
                >
                  {{ t('auth.forgotPassword') }}
                </el-button>
                <span class="text-stone-300 select-none">|</span>
                <el-button
                  type="primary"
                  link
                  @click="showSmsLogin"
                >
                  {{ t('auth.smsLogin') }}
                </el-button>
                <span class="text-stone-300 select-none">|</span>
                <el-button
                  type="primary"
                  link
                  @click="focusSesLogin"
                >
                  {{ t('auth.sesLogin') }}
                </el-button>
              </div>
            </form>

            <!-- Register Form -->
            <form
              v-if="currentView === 'register'"
              class="p-6 space-y-4"
              @submit.prevent="handleRegister"
            >
              <div
                v-if="registerRegionLoading"
                class="flex items-center gap-2 text-sm text-stone-500 py-1"
              >
                <Loader2 class="w-4 h-4 animate-spin shrink-0" />
                <span>{{ t('auth.modal.detectingRegion') }}</span>
              </div>

              <div
                v-if="!registerRegionLoading && isBothRegister"
                class="flex flex-wrap items-center justify-center gap-2"
                role="group"
                :aria-label="t('auth.modal.hybridRegisterGroupLabel')"
              >
                <button
                  type="button"
                  class="rounded-full px-4 py-2 text-xs font-medium transition-colors"
                  :class="
                    registerPath === 'email'
                      ? 'bg-stone-900 text-white'
                      : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                  "
                  @click="setRegisterPath('email')"
                >
                  {{ t('auth.modal.hybridRegisterEmailTab') }}
                </button>
                <button
                  type="button"
                  class="rounded-full px-4 py-2 text-xs font-medium transition-colors"
                  :class="
                    registerPath === 'phone'
                      ? 'bg-stone-900 text-white'
                      : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                  "
                  @click="setRegisterPath('phone')"
                >
                  {{ t('auth.modal.hybridRegisterPhoneTab') }}
                </button>
              </div>

              <div v-if="showMainlandPhoneFlow">
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="register-phone"
                >
                  {{ t('auth.phone') }} *
                </label>
                <input
                  id="register-phone"
                  v-model="registerForm.phone"
                  type="tel"
                  name="register-phone"
                  :placeholder="t('auth.modal.phonePlaceholder11')"
                  maxlength="11"
                  autocomplete="username"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div v-if="showOverseasEmailFlow">
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="register-education-email"
                >
                  {{ t('auth.modal.registrationEmailLabel') }}
                </label>
                <input
                  id="register-education-email"
                  v-model="registerForm.registrationEmail"
                  type="email"
                  name="register-education-email"
                  autocomplete="email"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
                <p
                  v-if="registrationEmailHint"
                  class="text-xs text-stone-500 mt-1.5 leading-relaxed"
                >
                  {{ registrationEmailHint }}
                </p>
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="register-password"
                >
                  {{ t('auth.password') }} *
                </label>
                <div class="relative">
                  <input
                    id="register-password"
                    v-model="registerForm.password"
                    :type="showPassword ? 'text' : 'password'"
                    name="register-password"
                    :placeholder="t('auth.modal.passwordMinPlaceholder')"
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
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="register-name"
                >
                  {{ t('auth.name') }} *
                </label>
                <input
                  id="register-name"
                  v-model="registerForm.name"
                  type="text"
                  name="register-name"
                  :placeholder="t('auth.modal.namePlaceholder')"
                  autocomplete="name"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div v-if="showMainlandPhoneFlow">
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="register-invitation-code"
                >
                  {{ t('auth.invitationCode') }} *
                </label>
                <input
                  id="register-invitation-code"
                  v-model="registerForm.invitationCode"
                  type="text"
                  name="register-invitation-code"
                  :placeholder="t('auth.modal.invitationPlaceholder')"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="register-captcha"
                >
                  {{ t('auth.captcha') }} *
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    id="register-captcha"
                    v-model="registerForm.captcha"
                    type="text"
                    name="register-captcha"
                    :placeholder="t('auth.modal.captchaPlaceholderShort')"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    :alt="t('auth.captcha')"
                    class="captcha-image"
                    :title="t('auth.clickToRefresh')"
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

              <template v-if="showOverseasEmailFlow">
                <div class="flex gap-2 items-end">
                  <div class="flex-1">
                    <label
                      class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                      for="register-email-code"
                    >
                      {{ t('auth.modal.emailCodeLabel') }} *
                    </label>
                    <input
                      id="register-email-code"
                      v-model="registerForm.emailCode"
                      type="text"
                      name="register-email-code"
                      maxlength="6"
                      inputmode="numeric"
                      autocomplete="one-time-code"
                      class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                    />
                  </div>
                  <button
                    type="button"
                    class="shrink-0 py-3 px-3 text-sm font-medium rounded-lg border border-stone-200 text-stone-800 hover:bg-stone-50 disabled:opacity-50"
                    :disabled="emailSending || emailCountdown > 0"
                    @click="sendRegisterEmailCode"
                  >
                    {{
                      emailCountdown > 0
                        ? t('auth.modal.resendIn', { seconds: emailCountdown })
                        : t('auth.modal.sendEmailCode')
                    }}
                  </button>
                </div>
                <label
                  class="flex items-start gap-2 cursor-pointer text-xs text-stone-500 leading-relaxed"
                >
                  <input
                    v-model="registerForm.outsideMainlandAcknowledged"
                    type="checkbox"
                    class="mt-0.5 shrink-0 rounded border-stone-300"
                  />
                  <span class="min-w-0">{{ overseasAcknowledgeCheckboxLabel }}</span>
                </label>
              </template>

              <p
                v-if="showMainlandPhoneFlow"
                class="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 leading-relaxed"
              >
                {{ t('auth.modal.mainlandSalesNotice') }}
              </p>

              <button
                type="submit"
                :disabled="isLoading || registerRegionLoading || registerRegion === null"
                class="w-full py-3 px-4 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 active:bg-stone-950 focus:ring-2 focus:ring-stone-900 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Loader2
                  v-if="isLoading"
                  class="w-4 h-4 animate-spin"
                />
                {{ isLoading ? t('auth.modal.registering') : t('auth.register') }}
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
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="sms-login-phone"
                >
                  {{ t('auth.loginPhoneOrEmail') }}
                </label>
                <input
                  id="sms-login-phone"
                  v-model="smsLoginForm.phone"
                  type="text"
                  name="sms-login-phone"
                  :placeholder="
                    smsLoginUsesEmail
                      ? t('auth.modal.forgotPhoneOrEmailPlaceholder')
                      : t('auth.modal.phoneRegisteredPlaceholder')
                  "
                  :maxlength="smsLoginUsesEmail ? 254 : 11"
                  inputmode="text"
                  autocomplete="username"
                  :disabled="smsSent"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all disabled:opacity-60"
                />
              </div>

              <div v-if="!smsSent">
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="sms-login-captcha"
                >
                  {{ t('auth.captcha') }}
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    id="sms-login-captcha"
                    v-model="smsLoginForm.captcha"
                    type="text"
                    name="sms-login-captcha"
                    :placeholder="t('auth.modal.captchaPlaceholderShort')"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    :alt="t('auth.captcha')"
                    class="captcha-image"
                    :title="t('auth.clickToRefresh')"
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
                {{
                  smsSending
                    ? smsLoginUsesEmail
                      ? t('auth.modal.sendingEmailCode')
                      : t('auth.modal.sendingSms')
                    : smsLoginUsesEmail
                      ? t('auth.modal.sendEmailCode')
                      : t('auth.modal.sendSmsCode')
                }}
              </button>

              <template v-if="smsSent">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                    for="sms-login-code"
                  >
                    {{
                      smsLoginUsesEmail
                        ? t('auth.modal.emailCodeLabel')
                        : t('auth.modal.smsCodeLabel')
                    }}
                  </label>
                  <input
                    id="sms-login-code"
                    v-model="smsLoginForm.smsCode"
                    type="text"
                    name="sms-login-code"
                    :placeholder="
                      smsLoginUsesEmail
                        ? t('auth.modal.emailCodePlaceholder')
                        : t('auth.modal.smsCodePlaceholder')
                    "
                    maxlength="6"
                    autocomplete="one-time-code"
                    class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <p class="text-xs text-stone-400 mt-1">
                    {{ t('auth.modal.codeSentTo') }}
                    {{ maskIdentifierForCodeSent(smsLoginForm.phone) }}
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
                  {{ isLoading ? t('auth.modal.loggingIn') : t('auth.login') }}
                </button>

                <div class="text-center">
                  <button
                    type="button"
                    :disabled="smsCountdown > 0"
                    class="text-sm text-stone-500 hover:text-stone-900 transition-colors disabled:opacity-50"
                    @click="sendSmsCode('login')"
                  >
                    {{
                      smsCountdown > 0
                        ? t('auth.modal.resendIn', { seconds: smsCountdown })
                        : t('auth.modal.resendCaptcha')
                    }}
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
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="forgot-phone"
                >
                  {{ t('auth.loginPhoneOrEmail') }}
                </label>
                <input
                  id="forgot-phone"
                  v-model="forgotForm.phone"
                  type="text"
                  name="forgot-phone"
                  :placeholder="t('auth.modal.forgotPhoneOrEmailPlaceholder')"
                  maxlength="254"
                  inputmode="text"
                  autocomplete="username"
                  :disabled="smsSent"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all disabled:opacity-60"
                />
              </div>

              <div v-if="!smsSent">
                <label
                  class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                  for="forgot-captcha"
                >
                  {{ t('auth.captcha') }}
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    id="forgot-captcha"
                    v-model="forgotForm.captcha"
                    type="text"
                    name="forgot-captcha"
                    :placeholder="t('auth.modal.captchaPlaceholderShort')"
                    maxlength="4"
                    class="flex-1 px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <img
                    v-if="captchaImage && !captchaLoading"
                    :src="captchaImage"
                    :alt="t('auth.captcha')"
                    class="captcha-image"
                    :title="t('auth.clickToRefresh')"
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
                {{
                  smsSending
                    ? t('auth.modal.sendingVerificationCode')
                    : t('auth.modal.sendVerificationCode')
                }}
              </button>

              <template v-if="smsSent">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                    for="forgot-sms-code"
                  >
                    {{
                      forgotUsesEmail ? t('auth.modal.emailCodeLabel') : t('auth.modal.smsCodeLabel')
                    }}
                  </label>
                  <input
                    id="forgot-sms-code"
                    v-model="forgotForm.smsCode"
                    type="text"
                    name="forgot-sms-code"
                    :placeholder="t('auth.modal.smsCodePlaceholder')"
                    maxlength="6"
                    autocomplete="one-time-code"
                    class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                </div>

                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                    for="forgot-new-password"
                  >
                    {{ t('auth.modal.newPassword') }}
                  </label>
                  <div class="relative">
                    <input
                      id="forgot-new-password"
                      v-model="forgotForm.newPassword"
                      :type="showPassword ? 'text' : 'password'"
                      name="forgot-new-password"
                      :placeholder="t('auth.modal.passwordMinPlaceholder')"
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
                    class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
                    for="forgot-confirm-password"
                  >
                    {{ t('auth.modal.confirmPassword') }}
                  </label>
                  <div class="relative">
                    <input
                      id="forgot-confirm-password"
                      v-model="forgotForm.confirmPassword"
                      :type="showConfirmPassword ? 'text' : 'password'"
                      name="forgot-confirm-password"
                      :placeholder="t('auth.modal.confirmPasswordPlaceholder')"
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
                  {{ isLoading ? t('auth.modal.resetting') : t('auth.resetPassword') }}
                </button>

                <div class="text-center">
                  <button
                    type="button"
                    :disabled="smsCountdown > 0"
                    class="text-sm text-stone-500 hover:text-stone-900 transition-colors disabled:opacity-50"
                    @click="sendSmsCode('reset')"
                  >
                    {{
                      smsCountdown > 0
                        ? t('auth.modal.resendIn', { seconds: smsCountdown })
                        : t('auth.modal.resendCaptcha')
                    }}
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

/* Login / Register segmented control — full-width 50/50, no third-party tab layout */
.auth-tab-switch {
  display: flex;
  width: 100%;
  box-sizing: border-box;
  border-bottom: 1px solid #e7e5e4;
}

.auth-tab-switch__btn {
  flex: 1 1 0;
  min-width: 0;
  margin: 0;
  padding: 0.75rem 0.5rem;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.25;
  color: #a8a29e;
  text-align: center;
  cursor: pointer;
  transition:
    color 0.2s ease,
    border-color 0.2s ease;
}

.auth-tab-switch__btn:hover {
  color: #78716c;
}

.auth-tab-switch__btn--active {
  color: #1c1917;
  border-bottom-color: #1c1917;
}

/* Element Plus Link Buttons - Swiss Design Override */
.el-button.is-link {
  --el-button-text-color: #78716c;
  --el-button-hover-text-color: #1c1917;
  --el-button-active-text-color: #1c1917;
  font-size: 14px;
  padding: 4px 8px;
}

/* Page header - Swiss Design style (single row: back + optional title) */
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
  inset-inline-end: 12px;
  z-index: 10;
  --el-button-text-color: #a8a29e;
  --el-button-hover-text-color: #57534e;
  --el-button-hover-bg-color: #f5f5f4;
}
</style>
