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
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ArrowLeft, Eye, EyeOff, GraduationCap, Loader2, LogIn, RefreshCw, UserRound } from '@lucide/vue'

import LoginAuthAltLinks from '@/components/auth/LoginAuthAltLinks.vue'
import OAuthQrLoginModal from '@/components/auth/OAuthQrLoginModal.vue'
import I18nText from '@/components/common/I18nText.vue'
import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLoginModal } from '@/composables/auth/useLoginModal'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { isTrainingInlineHost } from '@/composables/training/trainingInlineHost'
import { invitationCodeFromSearch } from '@/utils/invitationCode'
import { initCatWalk } from '@/utils/mascot/catWalk'
import { resolveOAuthInviteCode, shouldShowWechatLoginLink } from '@/utils/oauthLoginUi'

const props = defineProps<{
  visible: boolean
  /**
   * `/auth`: no full-screen scrim — page background stays fully visible.
   * Default uses a dark scrim (`stone-900/70`) for session-expired and other overlays.
   */
  lightBackdrop?: boolean
  /**
   * Dedicated `/auth` route: primary sign-in button reads “同意协议并登录”.
   */
  authPage?: boolean
  /**
   * When true, clicking outside the modal does nothing (no backdrop dismiss).
   * Use on dedicated auth pages where dismissing the modal has no sensible fallback.
   */
  persistent?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
  (e: 'contact'): void
}>()

const {
  authStore,
  t,
  currentView,
  activeTab,
  loginAudience,
  showLoginAudienceTabs,
  loginForm,
  studentLoginForm,
  registerForm,
  smsLoginForm,
  forgotForm,
  rememberAccount,
  agreeToTerms,
  captchaImage,
  captchaLoading,
  captchaLoadFailed,
  smsSending,
  smsCountdown,
  smsSent,
  isLoading,
  showPassword,
  showConfirmPassword,
  isVisible,
  loginSubmitLabel,
  pageHeaderTitle,
  closeModal,
  switchLoginRegisterTab,
  switchLoginAudience,
  registrationEnabledUi,
  showSmsLogin,
  showForgotPassword,
  backToLogin,
  refreshCaptcha,
  retryCaptcha,
  onCaptchaImageError,
  showLegacyCaptcha,
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
  hybridRegisterEmailTabLabel,
  registrationEmailLabel,
  registrationEmailHint,
  emailSending,
  emailCountdown,
  handleResetPassword,
} = useLoginModal(props, emit)

const route = useRoute()
const { featureWechatLogin } = useFeatureFlags()

const showQrLoginModal = ref(false)

const oauthInviteCode = computed(() =>
  resolveOAuthInviteCode(route.query.invite, registerForm.value.invitationCode)
)

watch(
  () => route.query.invite,
  (invite) => {
    const raw = typeof invite === 'string' ? invite : ''
    const code = invitationCodeFromSearch(`?invite=${encodeURIComponent(raw)}`)
    if (code && !registerForm.value.invitationCode) {
      registerForm.value.invitationCode = code
    }
  },
  { immediate: true }
)

function openWechatQrLogin(): void {
  showQrLoginModal.value = true
}

function onQrLoginSuccess(): void {
  showQrLoginModal.value = false
  emit('success')
}

type SwissGlassCardExpose = {
  getCardEl: () => HTMLElement | null
  getOverlayEl: () => HTMLElement | null
}

const loginGlassCardRef = ref<SwissGlassCardExpose | null>(null)
const loginFormRef = ref<HTMLFormElement | null>(null)
const loginSubmitRef = ref<HTMLButtonElement | null>(null)

/** `/auth`: footer legal link sits below the modal — overlay must not swallow clicks. */
const passThroughFooterClicks = computed(() => Boolean(props.lightBackdrop && props.persistent))
const inlineHost = isTrainingInlineHost()
/** Dedicated `/auth` page: embed form in the white card (no teleport / glass hero). */
const authPageInline = computed(() => Boolean(props.authPage))
const embedInline = computed(() => inlineHost || authPageInline.value)

let disposeLoginCatWalk: (() => void) | undefined

watch(
  [isVisible, currentView, authPageInline],
  async ([visible, view, inlineAuth]) => {
    disposeLoginCatWalk?.()
    disposeLoginCatWalk = undefined
    // Skip roof-cat on `/auth` white card — track chrome was covering the form.
    if (!visible || view !== 'login' || inlineAuth) return
    await nextTick()
    await nextTick()
    const card = loginGlassCardRef.value?.getCardEl()
    const overlay = loginGlassCardRef.value?.getOverlayEl()
    const form = loginFormRef.value
    const submitBtn = loginSubmitRef.value
    if (
      !(card instanceof HTMLElement) ||
      !(overlay instanceof HTMLElement) ||
      !form ||
      !submitBtn
    ) {
      return
    }
    const phone = form.querySelector('#login-phone')
    const password = form.querySelector('#login-password')
    if (!(phone instanceof HTMLInputElement) || !(password instanceof HTMLInputElement)) return
    disposeLoginCatWalk = initCatWalk({
      trackRoot: card,
      submitButton: submitBtn,
      typingInputs: [phone, password],
      form,
      mountParent: document.body,
      roofWalk: true,
    })
  },
  { flush: 'post', immediate: true }
)

onBeforeUnmount(() => {
  disposeLoginCatWalk?.()
})

function openLogin(): void {
  switchLoginAudience('teacher')
  switchLoginRegisterTab('login')
}

function openRegister(): void {
  switchLoginAudience('teacher')
  if (registrationEnabledUi.value) {
    switchLoginRegisterTab('register')
  }
}

defineExpose({ openLogin, openRegister })
</script>

<template>
  <SwissGlassCard
    ref="loginGlassCardRef"
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.login.ribbon')"
    ribbon-key="swissGlass.hero.login.ribbon"
    :title="t('swissGlass.hero.login.title')"
    title-key="swissGlass.hero.login.title"
    :line1="t('swissGlass.hero.login.line1')"
    line1-key="swissGlass.hero.login.line1"
    :icon="LogIn"
    :light-backdrop="lightBackdrop"
    :persistent="persistent"
    :show-close="!authPage"
    :hide-hero="authPageInline"
    :teleport-disabled="embedInline"
    :overlay-class="
      [
        'swiss-glass-card-overlay--auth',
        // Training host only: absolute fill. Never on `/auth` (collapses the white card).
        inlineHost ? 'swiss-glass-card-overlay--contained' : '',
        authPageInline ? 'swiss-glass-card-overlay--auth-split' : '',
        passThroughFooterClicks ? 'pointer-events-none' : '',
        authStore.showSessionExpiredModal ? 'pointer-events-auto' : '',
        lightBackdrop && !authPageInline ? 'swiss-glass-card-overlay--auth-pad' : '',
      ]
        .filter(Boolean)
        .join(' ')
    "
    :card-class="
      [
        'swiss-glass-card--auth',
        authPageInline ? 'swiss-glass-card--auth-split' : '',
        passThroughFooterClicks ? 'pointer-events-auto' : '',
      ]
        .filter(Boolean)
        .join(' ')
    "
    @close="closeModal"
  >
    <div :class="{ 'auth-page-form': authPageInline }">
      <!-- /auth card primary tabs: Teacher | Student -->
      <div
        v-if="authPageInline && showLoginAudienceTabs && currentView === 'login'"
        class="auth-tab-switch auth-tab-switch--soft"
        :class="{ 'auth-tab-switch--soft-end': loginAudience === 'student' }"
        role="tablist"
        :aria-label="t('auth.loginAudience')"
      >
        <span
          class="auth-tab-switch__thumb"
          aria-hidden="true"
        />
        <button
          type="button"
          role="tab"
          :aria-selected="loginAudience === 'teacher'"
          class="auth-tab-switch__btn"
          :class="{ 'auth-tab-switch__btn--active': loginAudience === 'teacher' }"
          @click="switchLoginAudience('teacher')"
        >
          <GraduationCap
            class="auth-tab-switch__icon"
            aria-hidden="true"
          />
          {{ t('auth.landing.teacherLoginTab') }}
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="loginAudience === 'student'"
          class="auth-tab-switch__btn"
          :class="{ 'auth-tab-switch__btn--active': loginAudience === 'student' }"
          @click="switchLoginAudience('student')"
        >
          <UserRound
            class="auth-tab-switch__icon"
            aria-hidden="true"
          />
          {{ t('auth.landing.studentLoginTab') }}
        </button>
      </div>

      <!-- Overlay / non-auth: Teacher / Student audience -->
      <div
        v-if="!authPageInline && showLoginAudienceTabs && currentView === 'login'"
        class="auth-tab-switch"
        role="tablist"
        :aria-label="t('auth.loginAudience')"
      >
        <button
          type="button"
          role="tab"
          :aria-selected="loginAudience === 'teacher'"
          class="auth-tab-switch__btn"
          :class="{ 'auth-tab-switch__btn--active': loginAudience === 'teacher' }"
          @click="switchLoginAudience('teacher')"
        >
          {{ t('auth.loginAudienceTeacher') }}
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="loginAudience === 'student'"
          class="auth-tab-switch__btn"
          :class="{ 'auth-tab-switch__btn--active': loginAudience === 'student' }"
          @click="switchLoginAudience('student')"
        >
          {{ t('auth.loginAudienceStudent') }}
        </button>
      </div>

      <!-- Overlay modal: Login / Register switch -->
      <div
        v-if="
          !authPageInline &&
          registrationEnabledUi &&
          (currentView === 'login' || currentView === 'register') &&
          loginAudience === 'teacher'
        "
        class="auth-tab-switch"
        role="tablist"
        :aria-label="t('auth.loginRegister')"
      >
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'login'"
          class="auth-tab-switch__btn"
          data-training-target="auth-login"
          :class="{ 'auth-tab-switch__btn--active': activeTab === 'login' }"
          @click="switchLoginRegisterTab('login')"
        >
          <I18nText k="auth.login" />
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'register'"
          class="auth-tab-switch__btn"
          data-training-target="auth-register"
          :class="{ 'auth-tab-switch__btn--active': activeTab === 'register' }"
          @click="switchLoginRegisterTab('register')"
        >
          <I18nText k="auth.register" />
        </button>
      </div>
      <div
        v-else-if="
          !authPageInline &&
          (currentView === 'login' || currentView === 'register') &&
          loginAudience === 'teacher' &&
          !showLoginAudienceTabs
        "
        class="auth-tab-switch"
        role="tablist"
        :aria-label="t('auth.login')"
      >
        <button
          type="button"
          role="tab"
          :aria-selected="true"
          class="auth-tab-switch__btn auth-tab-switch__btn--active"
        >
          <I18nText k="auth.login" />
        </button>
      </div>

      <!-- Sub-view header: back control is icon + label on one line (not el-page-header — it stacks title). -->
      <div
        v-if="
          currentView === 'sms-login' ||
          currentView === 'forgot-password' ||
          (authPageInline && currentView === 'register')
        "
        class="page-header"
        :class="{ 'page-header--auth': authPageInline }"
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
            <I18nText k="auth.backToLogin" />
          </button>
          <span
            v-if="currentView === 'sms-login'"
            class="page-header-title"
          >
            {{ pageHeaderTitle }}
          </span>
          <span
            v-else-if="authPageInline && currentView === 'register'"
            class="page-header-title"
          >
            {{ t('auth.register') }}
          </span>
        </div>
      </div>

      <!-- Teacher Login Form -->
      <form
        v-if="currentView === 'login' && loginAudience === 'teacher'"
        ref="loginFormRef"
        class="space-y-4"
        :class="authPageInline ? 'auth-page-teacher' : 'p-6'"
        @submit.prevent="handleLogin"
      >
        <div>
          <label
            class="block text-xs font-medium tracking-wide mb-2"
            :class="authPageInline ? 'auth-page-teacher__label' : 'text-stone-500'"
            for="login-phone"
          >
            <I18nText k="auth.loginPhoneOrEmail" />
          </label>
          <input
            id="login-phone"
            v-model="loginForm.phone"
            type="text"
            name="username"
            :placeholder="t('auth.modal.forgotPhoneOrEmailPlaceholder')"
            maxlength="254"
            autocomplete="username"
            class="w-full px-4 py-3 border-0 rounded-lg text-stone-900 placeholder-stone-400 transition-all"
            :class="
              authPageInline
                ? 'auth-page-teacher__input'
                : 'bg-stone-50 focus:ring-2 focus:ring-stone-900 focus:bg-white'
            "
          />
        </div>

        <div>
          <label
            class="block text-xs font-medium tracking-wide mb-2"
            :class="authPageInline ? 'auth-page-teacher__label' : 'text-stone-500'"
            for="login-password"
          >
            <I18nText k="auth.password" />
          </label>
          <div class="relative">
            <input
              id="login-password"
              v-model="loginForm.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              :placeholder="t('auth.modal.passwordPlaceholder')"
              autocomplete="current-password"
              class="w-full px-4 py-3 pr-12 border-0 rounded-lg text-stone-900 placeholder-stone-400 transition-all"
              :class="
                authPageInline
                  ? 'auth-page-teacher__input'
                  : 'bg-stone-50 focus:ring-2 focus:ring-stone-900 focus:bg-white'
              "
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
              :class="{ 'auth-page-teacher__eye': authPageInline }"
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

        <div
          v-if="authPageInline"
          class="auth-page-teacher__prefs"
        >
          <label class="auth-page-remember">
            <input
              v-model="rememberAccount"
              type="checkbox"
              class="auth-page-remember__box"
            />
            {{ t('auth.landing.rememberAccount') }}
          </label>
        </div>

        <label
          v-if="authPageInline"
          class="auth-page-teacher__agree"
        >
          <input
            v-model="agreeToTerms"
            type="checkbox"
            class="auth-page-remember__box"
          />
          <span>
            {{ t('auth.landing.agreeTermsPrefix') }}
            <RouterLink
              to="/privacy"
              target="_blank"
              rel="noopener noreferrer"
              class="auth-page-teacher__agree-link"
              @click.stop
            >
              {{ t('auth.softwareAgreementLink') }}
            </RouterLink>
          </span>
        </label>

        <div
          v-else
          class="flex items-center justify-between"
        >
          <label class="auth-page-remember text-stone-500">
            <input
              v-model="rememberAccount"
              type="checkbox"
              class="auth-page-remember__box"
            />
            {{ t('auth.landing.rememberAccount') }}
          </label>
        </div>

        <div v-if="showLegacyCaptcha">
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="login-captcha"
          >
            <I18nText k="auth.captcha" />
          </label>
          <div class="captcha-row">
            <input
              id="login-captcha"
              v-model="loginForm.captcha"
              type="text"
              name="login-captcha"
              :placeholder="t('auth.modal.captchaPlaceholderShort')"
              maxlength="4"
              class="captcha-row__input px-4 py-3 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
              :class="authPageInline ? 'auth-page-teacher__input' : 'bg-stone-50'"
            />
            <img
              v-if="captchaImage"
              :src="captchaImage"
              :alt="t('auth.captcha')"
              class="captcha-image"
              :class="{ 'captcha-image--loading': captchaLoading }"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
              @error="onCaptchaImageError"
            />
            <div
              v-else
              class="captcha-placeholder"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
            >
              <Loader2
                v-if="captchaLoading"
                class="w-5 h-5 text-stone-400 animate-spin"
              />
              <template v-else>
                <RefreshCw class="w-4 h-4 text-stone-400" />
                <span class="captcha-placeholder__hint">
                  {{
                    captchaLoadFailed
                      ? t('auth.modal.captchaLoadFailed')
                      : t('auth.clickToRefresh')
                  }}
                </span>
              </template>
            </div>
          </div>
        </div>

        <button
          ref="loginSubmitRef"
          type="submit"
          :disabled="isLoading"
          class="w-full py-3 px-4 text-white font-medium rounded-lg focus:ring-2 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          :class="
            authPageInline
              ? 'auth-page-cta'
              : 'bg-stone-900 hover:bg-stone-800 active:bg-stone-950 focus:ring-stone-900'
          "
        >
          <Loader2
            v-if="isLoading"
            class="w-4 h-4 animate-spin"
          />
          <I18nText
            v-if="isLoading"
            k="auth.modal.loggingIn"
          />
          <template v-else>{{ loginSubmitLabel }}</template>
        </button>

        <LoginAuthAltLinks
          v-if="!authPageInline"
          :show-wechat-login="shouldShowWechatLoginLink(featureWechatLogin)"
          @forgot="showForgotPassword"
          @sms="showSmsLogin"
          @wechat="openWechatQrLogin"
        />
        <div
          v-else
          class="auth-page-teacher__footer"
        >
          <button
            type="button"
            class="auth-page-teacher__footer-link"
            @click="showForgotPassword"
          >
            {{ t('auth.forgotPassword') }}
          </button>
          <span
            class="auth-page-teacher__footer-sep"
            aria-hidden="true"
          >|</span>
          <button
            type="button"
            class="auth-page-teacher__footer-link"
            @click="showSmsLogin"
          >
            {{ t('auth.smsLogin') }}
          </button>
          <template v-if="shouldShowWechatLoginLink(featureWechatLogin)">
            <span
              class="auth-page-teacher__footer-sep"
              aria-hidden="true"
            >|</span>
            <button
              type="button"
              class="auth-page-teacher__footer-link"
              @click="openWechatQrLogin"
            >
              {{ t('auth.wechatLogin') }}
            </button>
          </template>
          <template v-if="registrationEnabledUi">
            <span
              class="auth-page-teacher__footer-sep"
              aria-hidden="true"
            >|</span>
            <button
              type="button"
              class="auth-page-teacher__footer-link auth-page-teacher__footer-link--accent"
              @click="switchLoginRegisterTab('register')"
            >
              {{ t('auth.landing.registerNow') }}
            </button>
          </template>
        </div>
      </form>

      <!-- Student Login Form -->
      <form
        v-if="currentView === 'login' && loginAudience === 'student' && showLoginAudienceTabs"
        class="space-y-4"
        :class="authPageInline ? 'auth-page-teacher' : 'p-6'"
        @submit.prevent="handleLogin"
      >
        <div
          v-if="authPageInline"
          class="auth-page-student__beta"
        >
          <span class="auth-page-student__beta-badge">{{ t('auth.landing.studentBetaBadge') }}</span>
          <span class="auth-page-student__beta-text">
            {{ t('auth.landing.studentBetaHintBefore') }}
            <button
              type="button"
              class="auth-page-student__beta-link"
              @click="emit('contact')"
            >
              {{ t('auth.landing.navContact') }}
            </button>
          </span>
        </div>

        <div>
          <label
            class="block text-xs font-medium tracking-wide mb-2"
            :class="authPageInline ? 'auth-page-teacher__label' : 'text-stone-500'"
            for="student-class-code"
          >
            {{ t('auth.studentClassCode') }}
          </label>
          <input
            id="student-class-code"
            v-model="studentLoginForm.classCode"
            type="text"
            name="class_code"
            :placeholder="t('auth.studentClassCodePlaceholder')"
            maxlength="16"
            autocomplete="off"
            class="w-full px-4 py-3 border-0 rounded-lg text-stone-900 placeholder-stone-400 transition-all uppercase"
            :class="
              authPageInline
                ? 'auth-page-teacher__input'
                : 'bg-stone-50 focus:ring-2 focus:ring-stone-900 focus:bg-white'
            "
          />
        </div>

        <div>
          <label
            class="block text-xs font-medium tracking-wide mb-2"
            :class="authPageInline ? 'auth-page-teacher__label' : 'text-stone-500'"
            for="student-name"
          >
            {{ t('auth.name') }}
          </label>
          <input
            id="student-name"
            v-model="studentLoginForm.name"
            type="text"
            name="name"
            :placeholder="t('auth.modal.namePlaceholder')"
            maxlength="100"
            autocomplete="name"
            class="w-full px-4 py-3 border-0 rounded-lg text-stone-900 placeholder-stone-400 transition-all"
            :class="
              authPageInline
                ? 'auth-page-teacher__input'
                : 'bg-stone-50 focus:ring-2 focus:ring-stone-900 focus:bg-white'
            "
          />
        </div>

        <div>
          <label
            class="block text-xs font-medium tracking-wide mb-2"
            :class="authPageInline ? 'auth-page-teacher__label' : 'text-stone-500'"
            for="student-password"
          >
            {{ t('auth.password') }}
          </label>
          <div class="relative">
            <input
              id="student-password"
              v-model="studentLoginForm.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              :placeholder="t('auth.modal.passwordPlaceholder')"
              autocomplete="current-password"
              class="w-full px-4 py-3 pr-12 border-0 rounded-lg text-stone-900 placeholder-stone-400 transition-all"
              :class="
                authPageInline
                  ? 'auth-page-teacher__input'
                  : 'bg-stone-50 focus:ring-2 focus:ring-stone-900 focus:bg-white'
              "
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600 transition-colors"
              :class="{ 'auth-page-teacher__eye': authPageInline }"
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

        <div v-if="showLegacyCaptcha">
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="student-captcha"
          >
            {{ t('auth.captcha') }}
          </label>
          <div class="captcha-row">
            <input
              id="student-captcha"
              v-model="studentLoginForm.captcha"
              type="text"
              name="student-captcha"
              :placeholder="t('auth.modal.captchaPlaceholderShort')"
              maxlength="4"
              class="captcha-row__input px-4 py-3 border-0 rounded-lg text-stone-900 placeholder-stone-400 transition-all"
              :class="authPageInline ? 'auth-page-teacher__input' : 'bg-stone-50 focus:ring-2 focus:ring-stone-900 focus:bg-white'"
            />
            <img
              v-if="captchaImage"
              :src="captchaImage"
              :alt="t('auth.captcha')"
              class="captcha-image"
              :class="{ 'captcha-image--loading': captchaLoading }"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
              @error="onCaptchaImageError"
            />
            <div
              v-else
              class="captcha-placeholder"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
            >
              <Loader2
                v-if="captchaLoading"
                class="w-5 h-5 text-stone-400 animate-spin"
              />
              <template v-else>
                <RefreshCw class="w-4 h-4 text-stone-400" />
                <span class="captcha-placeholder__hint">
                  {{
                    captchaLoadFailed
                      ? t('auth.modal.captchaLoadFailed')
                      : t('auth.clickToRefresh')
                  }}
                </span>
              </template>
            </div>
          </div>
        </div>

        <button
          type="submit"
          :disabled="isLoading"
          class="w-full py-3 px-4 text-white font-medium rounded-lg focus:ring-2 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          :class="
            authPageInline
              ? 'auth-page-cta'
              : 'bg-stone-900 hover:bg-stone-800 active:bg-stone-950 focus:ring-stone-900'
          "
        >
          <Loader2
            v-if="isLoading"
            class="w-4 h-4 animate-spin"
          />
          {{
            isLoading
              ? t('auth.modal.loggingIn')
              : authPageInline
                ? t('auth.login')
                : loginSubmitLabel
          }}
        </button>
      </form>

      <!-- Register Form -->
      <form
        v-if="currentView === 'register'"
        class="space-y-4"
        :class="authPageInline ? 'auth-page-teacher' : 'p-6'"
        @submit.prevent="handleRegister"
      >
        <div
          v-if="registerRegionLoading"
          class="flex items-center gap-2 text-sm text-stone-500 py-1"
        >
          <Loader2 class="w-4 h-4 animate-spin shrink-0" />
          <span><I18nText k="auth.modal.detectingRegion" /></span>
        </div>

        <div
          v-if="!registerRegionLoading && isBothRegister && authPageInline"
          class="auth-tab-switch auth-tab-switch--soft"
          :class="{ 'auth-tab-switch--soft-end': registerPath === 'phone' }"
          role="group"
          :aria-label="t('auth.modal.hybridRegisterGroupLabel')"
        >
          <span
            class="auth-tab-switch__thumb"
            aria-hidden="true"
          />
          <button
            type="button"
            class="auth-tab-switch__btn"
            :class="{ 'auth-tab-switch__btn--active': registerPath === 'email' }"
            @click="setRegisterPath('email')"
          >
            {{ hybridRegisterEmailTabLabel }}
          </button>
          <button
            type="button"
            class="auth-tab-switch__btn"
            :class="{ 'auth-tab-switch__btn--active': registerPath === 'phone' }"
            @click="setRegisterPath('phone')"
          >
            {{ t('auth.modal.hybridRegisterPhoneTab') }}
          </button>
        </div>
        <div
          v-else-if="!registerRegionLoading && isBothRegister"
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
            {{ hybridRegisterEmailTabLabel }}
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
            <I18nText k="auth.modal.hybridRegisterPhoneTab" />
          </button>
        </div>

        <div v-if="showMainlandPhoneFlow">
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="register-phone"
          >
            <I18nText k="auth.phone" /> *
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
            {{ registrationEmailLabel }}
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
            <I18nText k="auth.password" /> *
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
              :class="{ 'auth-page-teacher__eye': authPageInline }"
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
            <I18nText k="auth.name" /> *
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
            <I18nText k="auth.invitationCode" /> *
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

        <div v-if="showLegacyCaptcha">
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="register-captcha"
          >
            <I18nText k="auth.captcha" /> *
          </label>
          <div class="captcha-row">
            <input
              id="register-captcha"
              v-model="registerForm.captcha"
              type="text"
              name="register-captcha"
              :placeholder="t('auth.modal.captchaPlaceholderShort')"
              maxlength="4"
              class="captcha-row__input px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
            />
            <img
              v-if="captchaImage"
              :src="captchaImage"
              :alt="t('auth.captcha')"
              class="captcha-image"
              :class="{ 'captcha-image--loading': captchaLoading }"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
              @error="onCaptchaImageError"
            />
            <div
              v-else
              class="captcha-placeholder"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
            >
              <Loader2
                v-if="captchaLoading"
                class="w-5 h-5 text-stone-400 animate-spin"
              />
              <template v-else>
                <RefreshCw class="w-4 h-4 text-stone-400" />
                <span class="captcha-placeholder__hint">
                  {{
                    captchaLoadFailed
                      ? t('auth.modal.captchaLoadFailed')
                      : t('auth.clickToRefresh')
                  }}
                </span>
              </template>
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
                <I18nText k="auth.modal.emailCodeLabel" /> *
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
              class="shrink-0 py-3 px-3 text-sm font-medium rounded-lg disabled:opacity-50 transition-all"
              :class="
                authPageInline
                  ? 'auth-page-cta auth-page-cta--compact'
                  : 'border border-stone-200 text-stone-800 hover:bg-stone-50'
              "
              :disabled="emailSending || emailCountdown > 0"
              @click="sendRegisterEmailCode"
            >
              <I18nText
                v-if="emailCountdown > 0"
                k="auth.modal.resendIn"
                :params="{ seconds: emailCountdown }"
              />
              <I18nText
                v-else
                k="auth.modal.sendEmailCode"
              />
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
          <I18nText k="auth.modal.mainlandSalesNotice" />
        </p>

        <button
          type="submit"
          :disabled="isLoading || registerRegionLoading || registerRegion === null"
          class="w-full py-3 px-4 text-white font-medium rounded-lg focus:ring-2 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          :class="
            authPageInline
              ? 'auth-page-cta'
              : 'bg-stone-900 hover:bg-stone-800 active:bg-stone-950 focus:ring-stone-900'
          "
        >
          <Loader2
            v-if="isLoading"
            class="w-4 h-4 animate-spin"
          />
          <I18nText :k="isLoading ? 'auth.modal.registering' : 'auth.register'" />
        </button>
      </form>

      <!-- SMS Login Form -->
      <form
        v-if="currentView === 'sms-login'"
        class="space-y-4"
        :class="authPageInline ? 'auth-page-teacher' : 'p-6'"
        @submit.prevent="handleSmsLogin"
      >
        <div>
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="sms-login-phone"
          >
            <I18nText k="auth.loginPhoneOrEmail" />
          </label>
          <input
            id="sms-login-phone"
            v-model="smsLoginForm.phone"
            type="text"
            name="username"
            :placeholder="t('auth.modal.forgotPhoneOrEmailPlaceholder')"
            maxlength="254"
            inputmode="text"
            autocomplete="username"
            :disabled="smsSent"
            class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all disabled:opacity-60"
          />
        </div>

        <div v-if="!smsSent && showLegacyCaptcha">
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="sms-login-captcha"
          >
            <I18nText k="auth.captcha" />
          </label>
          <div class="captcha-row">
            <input
              id="sms-login-captcha"
              v-model="smsLoginForm.captcha"
              type="text"
              name="sms-login-captcha"
              :placeholder="t('auth.modal.captchaPlaceholderShort')"
              maxlength="4"
              class="captcha-row__input px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
            />
            <img
              v-if="captchaImage"
              :src="captchaImage"
              :alt="t('auth.captcha')"
              class="captcha-image"
              :class="{ 'captcha-image--loading': captchaLoading }"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
              @error="onCaptchaImageError"
            />
            <div
              v-else
              class="captcha-placeholder"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
            >
              <Loader2
                v-if="captchaLoading"
                class="w-5 h-5 text-stone-400 animate-spin"
              />
              <template v-else>
                <RefreshCw class="w-4 h-4 text-stone-400" />
                <span class="captcha-placeholder__hint">
                  {{
                    captchaLoadFailed
                      ? t('auth.modal.captchaLoadFailed')
                      : t('auth.clickToRefresh')
                  }}
                </span>
              </template>
            </div>
          </div>
        </div>

        <button
          v-if="!smsSent"
          type="button"
          :disabled="smsSending"
          class="w-full py-3 px-4 text-white font-medium rounded-lg focus:ring-2 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          :class="
            authPageInline
              ? 'auth-page-cta'
              : 'bg-stone-900 hover:bg-stone-800 active:bg-stone-950 focus:ring-stone-900'
          "
          @click="sendSmsCode('login')"
        >
          <Loader2
            v-if="smsSending"
            class="w-4 h-4 animate-spin"
          />
          <I18nText
            :k="
              smsSending
                ? smsLoginUsesEmail
                  ? 'auth.modal.sendingEmailCode'
                  : 'auth.modal.sendingVerificationCode'
                : smsLoginUsesEmail
                  ? 'auth.modal.sendEmailCode'
                  : 'auth.modal.sendVerificationCode'
            "
          />
        </button>

        <template v-if="smsSent">
          <div>
            <label
              class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
              for="sms-login-code"
            >
              <I18nText
                :k="smsLoginUsesEmail ? 'auth.modal.emailCodeLabel' : 'auth.modal.smsCodeLabel'"
              />
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
              <I18nText k="auth.modal.codeSentTo" />
              {{ maskIdentifierForCodeSent(smsLoginForm.phone) }}
            </p>
          </div>

          <button
            type="submit"
            :disabled="isLoading"
            class="w-full py-3 px-4 text-white font-medium rounded-lg focus:ring-2 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            :class="
              authPageInline
                ? 'auth-page-cta'
                : 'bg-stone-900 hover:bg-stone-800 active:bg-stone-950 focus:ring-stone-900'
            "
          >
            <Loader2
              v-if="isLoading"
              class="w-4 h-4 animate-spin"
            />
            <I18nText
              v-if="isLoading"
              k="auth.modal.loggingIn"
            />
            <template v-else>{{ loginSubmitLabel }}</template>
          </button>

          <div class="text-center">
            <button
              type="button"
              :disabled="smsCountdown > 0"
              class="text-sm text-stone-500 hover:text-stone-900 transition-colors disabled:opacity-50"
              @click="sendSmsCode('login')"
            >
              <I18nText
                v-if="smsCountdown > 0"
                k="auth.modal.resendIn"
                :params="{ seconds: smsCountdown }"
              />
              <I18nText
                v-else
                k="auth.modal.resendCaptcha"
              />
            </button>
          </div>
        </template>
      </form>

      <!-- Forgot Password Form -->
      <form
        v-if="currentView === 'forgot-password'"
        class="space-y-4"
        :class="authPageInline ? 'auth-page-teacher' : 'p-6'"
        @submit.prevent="handleResetPassword"
      >
        <div>
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="forgot-phone"
          >
            <I18nText k="auth.loginPhoneOrEmail" />
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

        <div v-if="!smsSent && showLegacyCaptcha">
          <label
            class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
            for="forgot-captcha"
          >
            <I18nText k="auth.captcha" />
          </label>
          <div class="captcha-row">
            <input
              id="forgot-captcha"
              v-model="forgotForm.captcha"
              type="text"
              name="forgot-captcha"
              :placeholder="t('auth.modal.captchaPlaceholderShort')"
              maxlength="4"
              class="captcha-row__input px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
            />
            <img
              v-if="captchaImage"
              :src="captchaImage"
              :alt="t('auth.captcha')"
              class="captcha-image"
              :class="{ 'captcha-image--loading': captchaLoading }"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
              @error="onCaptchaImageError"
            />
            <div
              v-else
              class="captcha-placeholder"
              :title="t('auth.clickToRefresh')"
              @click="retryCaptcha"
            >
              <Loader2
                v-if="captchaLoading"
                class="w-5 h-5 text-stone-400 animate-spin"
              />
              <template v-else>
                <RefreshCw class="w-4 h-4 text-stone-400" />
                <span class="captcha-placeholder__hint">
                  {{
                    captchaLoadFailed
                      ? t('auth.modal.captchaLoadFailed')
                      : t('auth.clickToRefresh')
                  }}
                </span>
              </template>
            </div>
          </div>
        </div>

        <button
          v-if="!smsSent"
          type="button"
          :disabled="smsSending"
          class="w-full py-3 px-4 text-white font-medium rounded-lg focus:ring-2 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          :class="
            authPageInline
              ? 'auth-page-cta'
              : 'bg-stone-900 hover:bg-stone-800 active:bg-stone-950 focus:ring-stone-900'
          "
          @click="sendSmsCode('reset')"
        >
          <Loader2
            v-if="smsSending"
            class="w-4 h-4 animate-spin"
          />
          <I18nText
            :k="
              smsSending
                ? forgotUsesEmail
                  ? 'auth.modal.sendingEmailCode'
                  : 'auth.modal.sendingVerificationCode'
                : forgotUsesEmail
                  ? 'auth.modal.sendEmailCode'
                  : 'auth.modal.sendVerificationCode'
            "
          />
        </button>

        <template v-if="smsSent">
          <div>
            <label
              class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
              for="forgot-sms-code"
            >
              <I18nText
                :k="forgotUsesEmail ? 'auth.modal.emailCodeLabel' : 'auth.modal.smsCodeLabel'"
              />
            </label>
            <input
              id="forgot-sms-code"
              v-model="forgotForm.smsCode"
              type="text"
              name="forgot-sms-code"
              :placeholder="
                forgotUsesEmail
                  ? t('auth.modal.emailCodePlaceholder')
                  : t('auth.modal.smsCodePlaceholder')
              "
              maxlength="6"
              autocomplete="one-time-code"
              class="w-full px-4 py-3 bg-stone-50 border-0 rounded-lg text-stone-900 placeholder-stone-400 focus:ring-2 focus:ring-stone-900 focus:bg-white transition-all"
            />
            <p class="text-xs text-stone-400 mt-1">
              <I18nText k="auth.modal.codeSentTo" />
              {{ maskIdentifierForCodeSent(forgotForm.phone) }}
            </p>
          </div>

          <div>
            <label
              class="block text-xs font-medium text-stone-500 tracking-wide mb-2"
              for="forgot-new-password"
            >
              <I18nText k="auth.modal.newPassword" />
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
              <I18nText k="auth.modal.confirmPassword" />
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
            class="w-full py-3 px-4 text-white font-medium rounded-lg focus:ring-2 focus:ring-offset-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            :class="
              authPageInline
                ? 'auth-page-cta'
                : 'bg-stone-900 hover:bg-stone-800 active:bg-stone-950 focus:ring-stone-900'
            "
          >
            <Loader2
              v-if="isLoading"
              class="w-4 h-4 animate-spin"
            />
            <I18nText :k="isLoading ? 'auth.modal.resetting' : 'auth.resetPassword'" />
          </button>

          <div class="text-center">
            <button
              type="button"
              :disabled="smsCountdown > 0"
              class="text-sm text-stone-500 hover:text-stone-900 transition-colors disabled:opacity-50"
              @click="sendSmsCode('reset')"
            >
              <I18nText
                v-if="smsCountdown > 0"
                k="auth.modal.resendIn"
                :params="{ seconds: smsCountdown }"
              />
              <I18nText
                v-else
                k="auth.modal.resendCaptcha"
              />
            </button>
          </div>
        </template>
      </form>
    </div>
  </SwissGlassCard>

  <OAuthQrLoginModal
    v-model:visible="showQrLoginModal"
    :invite-code="oauthInviteCode"
    initial-provider="wechat"
    lock-provider
    @success="onQrLoginSuccess"
  />
</template>

<style scoped>
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

.auth-tab-switch--soft {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  margin: 0 0 1rem;
  padding: 0.28rem;
  border: 0;
  border-radius: 1rem;
  background:
    linear-gradient(180deg, rgb(248 250 252 / 0.95), rgb(241 245 249 / 0.9));
  box-shadow: inset 0 1px 1px rgb(255 255 255 / 0.7);
}

.auth-tab-switch__thumb {
  position: absolute;
  top: 0.28rem;
  bottom: 0.28rem;
  left: 0.28rem;
  width: calc(50% - 0.28rem);
  border-radius: 0.78rem;
  background: #fff;
  box-shadow:
    0 1px 2px rgb(15 23 42 / 0.04),
    0 8px 20px rgb(99 102 241 / 0.12);
  transition: transform 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  pointer-events: none;
  z-index: 0;
}

.auth-tab-switch--soft-end .auth-tab-switch__thumb {
  transform: translateX(100%);
}

.auth-tab-switch--soft .auth-tab-switch__btn {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.72rem 0.65rem;
  border: 0;
  border-bottom: 0;
  border-radius: 0.78rem;
  color: #94a3b8;
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  background: transparent;
  transition:
    color 0.28s ease,
    transform 0.28s ease;
}

.auth-tab-switch--soft .auth-tab-switch__btn:hover {
  color: #64748b;
  background: transparent;
}

.auth-tab-switch--soft .auth-tab-switch__btn--active {
  color: #4338ca;
  background: transparent;
  box-shadow: none;
}

.auth-tab-switch--soft .auth-tab-switch__icon {
  width: 1.05rem;
  height: 1.05rem;
  opacity: 0.72;
  transition:
    opacity 0.28s ease,
    transform 0.38s cubic-bezier(0.22, 1, 0.36, 1);
}

.auth-tab-switch--soft .auth-tab-switch__btn--active .auth-tab-switch__icon {
  opacity: 1;
  transform: scale(1.06);
}

.auth-tab-switch__icon {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

.auth-page-form {
  width: 100%;
}

.auth-page-teacher {
  padding: 0.15rem 0 0.35rem;
}

.auth-page-teacher label.block,
.auth-page-teacher__label {
  color: #475569;
  font-weight: 600;
}

.auth-page-teacher :is(input[type='text'], input[type='email'], input[type='tel'], input[type='password']) {
  border-radius: 0.85rem !important;
  background: #eef2ff !important;
  box-shadow: none;
}

.auth-page-teacher
  :is(input[type='text'], input[type='email'], input[type='tel'], input[type='password']):focus {
  background: #fff !important;
  outline: none;
  box-shadow: 0 0 0 3px rgb(99 102 241 / 0.16);
}

.auth-page-teacher__input {
  border-radius: 0.85rem !important;
  background: #eef2ff !important;
  box-shadow: none;
}

.auth-page-teacher__input:focus {
  background: #fff !important;
  outline: none;
  box-shadow: 0 0 0 3px rgb(99 102 241 / 0.16);
}

.auth-page-teacher__eye {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.85rem;
  height: 1.85rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.4rem;
  background: rgb(255 255 255 / 0.7);
  color: #64748b;
}

.auth-page-teacher__eye:hover {
  color: #334155;
  border-color: #cbd5e1;
}

.auth-page-teacher__prefs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.85rem 1.25rem;
}

.auth-page-teacher__agree {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #64748b;
  cursor: pointer;
  user-select: none;
}

.auth-page-teacher__agree .auth-page-remember__box {
  margin-top: 0.15rem;
}

.auth-page-teacher__agree-link {
  color: #4f46e5;
  font-weight: 600;
  text-decoration: none;
}

.auth-page-teacher__agree-link:hover {
  color: #4338ca;
  text-decoration: underline;
}

.auth-page-cta,
.auth-page-teacher__submit {
  margin-top: 0.15rem;
  background: linear-gradient(90deg, #3b82f6 0%, #7c5cbf 100%) !important;
  border: 0 !important;
  border-radius: 0.75rem !important;
  color: #fff !important;
  font-weight: 700 !important;
  box-shadow: 0 10px 24px rgb(99 102 241 / 0.28);
}

.auth-page-cta:hover:not(:disabled),
.auth-page-teacher__submit:hover:not(:disabled) {
  filter: brightness(1.05);
}

.auth-page-cta--compact {
  margin-top: 0;
  min-width: 7.5rem;
  padding-inline: 0.85rem !important;
  box-shadow: 0 6px 16px rgb(99 102 241 / 0.22);
}

.auth-page-student__beta {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  margin: 0 0 0.15rem;
}

.auth-page-student__beta-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.18rem 0.5rem;
  border-radius: 0.4rem;
  background: linear-gradient(90deg, rgb(59 130 246 / 0.12), rgb(124 92 191 / 0.14));
  color: #4f46e5;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.2;
}

.auth-page-student__beta-text {
  font-size: 0.78rem;
  color: #94a3b8;
  line-height: 1.35;
}

.auth-page-student__beta-link {
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: #4f46e5;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.auth-page-student__beta-link:hover {
  color: #4338ca;
  text-decoration: underline;
}

.auth-page-teacher__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.45rem 0.55rem;
  padding-top: 0.15rem;
  font-size: 0.85rem;
}

.auth-page-teacher__footer-link {
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: #64748b;
  font: inherit;
  cursor: pointer;
}

.auth-page-teacher__footer-link:hover {
  color: #334155;
}

.auth-page-teacher__footer-link--accent {
  color: #4f46e5;
  font-weight: 600;
}

.auth-page-teacher__footer-link--accent:hover {
  color: #4338ca;
}

.auth-page-teacher__footer-sep {
  color: #cbd5e1;
  user-select: none;
}

.auth-page-remember {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: #64748b;
  cursor: pointer;
  user-select: none;
}

.auth-page-remember__box {
  width: 0.95rem;
  height: 0.95rem;
  accent-color: #6366f1;
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

.page-header--auth {
  margin: 0 0 0.85rem;
  padding: 0 0 0.75rem;
  border-bottom: 1px solid #e8eef6;
}

.page-header--auth .page-header__back {
  color: #64748b;
}

.page-header--auth .page-header__back:hover {
  color: #4f46e5;
}

.page-header--auth .page-header-title {
  color: #334155;
  font-weight: 700;
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
</style>
