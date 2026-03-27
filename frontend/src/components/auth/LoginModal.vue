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
import { ElPageHeader } from 'element-plus'

import { Close } from '@element-plus/icons-vue'

import { Eye, EyeOff, Loader2, RefreshCw } from 'lucide-vue-next'

import { useLoginModal } from '@/composables/auth/useLoginModal'

const props = defineProps<{
  visible: boolean
  /**
   * `/auth`: no full-screen scrim — page background stays fully visible; backdrop dismiss still works.
   * Default uses a dark scrim (`stone-900/70`) for session-expired and other overlays.
   */
  lightBackdrop?: boolean
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
  sendSmsCode,
  handleSmsLogin,
  handleResetPassword,
  handleBackdropClick,
} = useLoginModal(props, emit)
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
              <p class="text-xs text-stone-400 tracking-widest uppercase mt-1.5">
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
                  {{ t('auth.phone') }}
                </label>
                <input
                  v-model="loginForm.phone"
                  type="tel"
                  :placeholder="t('auth.modal.phonePlaceholder11')"
                  maxlength="11"
                  autocomplete="username"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.password') }}
                </label>
                <div class="relative">
                  <input
                    v-model="loginForm.password"
                    :type="showPassword ? 'text' : 'password'"
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
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.captcha') }}
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="loginForm.captcha"
                    type="text"
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
              <div class="flex justify-center items-center gap-1 pt-2">
                <el-button
                  type="primary"
                  link
                  @click="showForgotPassword"
                >
                  {{ t('auth.forgotPassword') }}
                </el-button>
                <span class="text-stone-300">|</span>
                <el-button
                  type="primary"
                  link
                  @click="showSmsLogin"
                >
                  {{ t('auth.smsLogin') }}
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
                  {{ t('auth.phone') }} *
                </label>
                <input
                  v-model="registerForm.phone"
                  type="tel"
                  :placeholder="t('auth.modal.phonePlaceholder11')"
                  maxlength="11"
                  autocomplete="username"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.password') }} *
                </label>
                <div class="relative">
                  <input
                    v-model="registerForm.password"
                    :type="showPassword ? 'text' : 'password'"
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
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.name') }} *
                </label>
                <input
                  v-model="registerForm.name"
                  type="text"
                  :placeholder="t('auth.modal.namePlaceholder')"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.invitationCode') }} *
                </label>
                <input
                  v-model="registerForm.invitationCode"
                  type="text"
                  :placeholder="t('auth.modal.invitationPlaceholder')"
                  class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.captcha') }} *
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="registerForm.captcha"
                    type="text"
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
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.phone') }}
                </label>
                <input
                  v-model="smsLoginForm.phone"
                  type="tel"
                  :placeholder="t('auth.modal.phoneRegisteredPlaceholder')"
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
                  {{ t('auth.captcha') }}
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="smsLoginForm.captcha"
                    type="text"
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
                {{ smsSending ? t('auth.modal.sendingSms') : t('auth.modal.sendSmsCode') }}
              </button>

              <template v-if="smsSent">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    {{ t('auth.modal.smsCodeLabel') }}
                  </label>
                  <input
                    v-model="smsLoginForm.smsCode"
                    type="text"
                    :placeholder="t('auth.modal.smsCodePlaceholder')"
                    maxlength="6"
                    class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                  <p class="text-xs text-stone-400 mt-1">
                    {{ t('auth.modal.codeSentTo') }}
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
                  class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                >
                  {{ t('auth.phone') }}
                </label>
                <input
                  v-model="forgotForm.phone"
                  type="tel"
                  :placeholder="t('auth.modal.phoneRegisteredPlaceholder')"
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
                  {{ t('auth.captcha') }}
                </label>
                <div class="flex gap-3 items-center">
                  <input
                    v-model="forgotForm.captcha"
                    type="text"
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
                {{ smsSending ? t('auth.modal.sendingSms') : t('auth.modal.sendSmsCode') }}
              </button>

              <template v-if="smsSent">
                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    {{ t('auth.modal.smsCodeLabel') }}
                  </label>
                  <input
                    v-model="forgotForm.smsCode"
                    type="text"
                    :placeholder="t('auth.modal.smsCodePlaceholder')"
                    maxlength="6"
                    class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
                  />
                </div>

                <div>
                  <label
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    {{ t('auth.modal.newPassword') }}
                  </label>
                  <div class="relative">
                    <input
                      v-model="forgotForm.newPassword"
                      :type="showPassword ? 'text' : 'password'"
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
                    class="block text-xs font-medium text-stone-500 uppercase tracking-wide mb-2"
                  >
                    {{ t('auth.modal.confirmPassword') }}
                  </label>
                  <div class="relative">
                    <input
                      v-model="forgotForm.confirmPassword"
                      :type="showConfirmPassword ? 'text' : 'password'"
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
