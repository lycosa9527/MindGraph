/**
 * State and handlers for LoginModal (password login, register, OTP sign-in, forgot password).
 *
 * OTP channels: SMS (Tencent SMS) sends an SMS code; email (Tencent SES) sends an email
 * verification code. User-facing copy uses “SMS code” vs “email verification code”; avoid
 * exposing provider acronyms (SES/SMS vendor) in UI strings.
 */
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { useRegisterRegionDetection } from '@/composables/auth/useRegisterRegionDetection'
import zhAuth from '@/locales/messages/zh/auth'
import { useAuthStore, useUIStore } from '@/stores'
import { isBrowserLanguageSimplifiedChinese } from '@/utils/clientRegion'

export type LoginModalViewState = 'login' | 'register' | 'sms-login' | 'forgot-password'

type LoginModalEmit = {
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}

export function useLoginModal(
  props: { visible: boolean; persistent?: boolean },
  emit: LoginModalEmit
) {
  const authStore = useAuthStore()
  const uiStore = useUIStore()
  const { t } = useLanguage()
  const notify = useNotifications()

  const currentView = ref<LoginModalViewState>('login')
  const activeTab = ref<string>('login')

  const loginForm = ref({
    phone: '',
    password: '',
    captcha: '',
  })

  const registerForm = ref({
    registrationEmail: '',
    phone: '',
    password: '',
    name: '',
    invitationCode: '',
    emailCode: '',
    outsideMainlandAcknowledged: false,
    captcha: '',
  })

  const smsLoginForm = ref({
    phone: '',
    captcha: '',
    smsCode: '',
  })

  const forgotForm = ref({
    phone: '',
    captcha: '',
    smsCode: '',
    newPassword: '',
    confirmPassword: '',
  })

  const captchaId = ref('')
  const captchaImage = ref('')
  const captchaLoading = ref(false)

  const smsSending = ref(false)
  const smsCountdown = ref(0)
  const smsCountdownTimer = ref<ReturnType<typeof setInterval> | null>(null)
  const smsSent = ref(false)

  const emailSending = ref(false)
  const emailCountdown = ref(0)
  const emailCountdownTimer = ref<ReturnType<typeof setInterval> | null>(null)

  const { registerRegion, registerRegionLoading, isBothRegister } = useRegisterRegionDetection(
    toRef(props, 'visible'),
    currentView
  )

  /** When region is unknown (GeoIP): user picks education email vs phone + invitation. */
  const registerPath = ref<'email' | 'phone'>('email')

  function setRegisterPath(path: 'email' | 'phone') {
    registerPath.value = path
  }

  const showOverseasEmailFlow = computed(
    () =>
      registerRegion.value === 'intl' ||
      (registerRegion.value === 'both' && registerPath.value === 'email')
  )

  const showMainlandPhoneFlow = computed(
    () =>
      registerRegion.value === 'cn' ||
      (registerRegion.value === 'both' && registerPath.value === 'phone')
  )

  const forgotUsesEmail = computed(() => {
    const id = forgotForm.value.phone.trim()
    return id.includes('@')
  })

  const smsLoginUsesEmail = computed(() => {
    const id = smsLoginForm.value.phone.trim()
    return id.includes('@')
  })

  const isLoading = ref(false)
  const showPassword = ref(false)
  const showConfirmPassword = ref(false)

  const isVisible = computed({
    get: () => props.visible,
    set: (value) => emit('update:visible', value),
  })

  const pageHeaderTitle = computed(() => {
    if (currentView.value === 'sms-login') {
      return smsLoginUsesEmail.value ? t('auth.sesLogin') : t('auth.smsLogin')
    }
    return t('auth.resetPassword')
  })

  function maskIdentifierForCodeSent(raw: string): string {
    const trimmed = raw.trim()
    if (trimmed.includes('@')) {
      const [localPart, domainPart] = trimmed.split('@')
      if (!domainPart) {
        return '***'
      }
      if (localPart.length <= 2) {
        return `***@${domainPart}`
      }
      return `${localPart[0]}***@${domainPart}`
    }
    return trimmed.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
  }

  /**
   * Overseas email registration: education-only wording for most browsers; full SC copy when the
   * browser language list indicates Simplified Chinese (see `isBrowserLanguageSimplifiedChinese`).
   */
  const overseasAcknowledgeCheckboxLabel = computed(() => {
    if (!showOverseasEmailFlow.value) {
      return ''
    }
    if (isBrowserLanguageSimplifiedChinese()) {
      const full = zhAuth['auth.modal.acknowledgeOverseasScBrowser']
      if (typeof full === 'string' && full.trim() !== '') {
        return full
      }
    }
    return t('auth.modal.acknowledgeOverseas')
  })

  function closeModal() {
    isVisible.value = false
    resetAllForms()
    currentView.value = 'login'
    activeTab.value = 'login'

    if (authStore.showSessionExpiredModal) {
      authStore.closeSessionExpiredModal()
      authStore.getAndClearPendingRedirect()
    }
  }

  function resetAllForms() {
    loginForm.value = { phone: '', password: '', captcha: '' }
    registerForm.value = {
      registrationEmail: '',
      phone: '',
      password: '',
      name: '',
      invitationCode: '',
      emailCode: '',
      outsideMainlandAcknowledged: false,
      captcha: '',
    }
    smsLoginForm.value = { phone: '', captcha: '', smsCode: '' }
    forgotForm.value = { phone: '', captcha: '', smsCode: '', newPassword: '', confirmPassword: '' }
    showPassword.value = false
    showConfirmPassword.value = false
    registerPath.value = 'email'
    smsSent.value = false
    smsCountdown.value = 0
    emailCountdown.value = 0
    if (smsCountdownTimer.value) {
      clearInterval(smsCountdownTimer.value)
      smsCountdownTimer.value = null
    }
    if (emailCountdownTimer.value) {
      clearInterval(emailCountdownTimer.value)
      emailCountdownTimer.value = null
    }
  }

  watch(
    () => [registerRegion.value, registerPath.value] as const,
    ([region, path]) => {
      if (region === 'intl' || (region === 'both' && path === 'email')) {
        registerForm.value.phone = ''
        registerForm.value.invitationCode = ''
      }
      if (region === 'cn' || (region === 'both' && path === 'phone')) {
        registerForm.value.registrationEmail = ''
        registerForm.value.emailCode = ''
        registerForm.value.outsideMainlandAcknowledged = false
      }
    }
  )

  function switchLoginRegisterTab(tab: 'login' | 'register') {
    activeTab.value = tab
    currentView.value = tab
    void refreshCaptcha()
  }

  function showSmsLogin() {
    currentView.value = 'sms-login'
    void refreshCaptcha()
  }

  function showForgotPassword() {
    currentView.value = 'forgot-password'
    void refreshCaptcha()
  }

  function backToLogin() {
    currentView.value = 'login'
    smsSent.value = false
    smsCountdown.value = 0
    if (smsCountdownTimer.value) {
      clearInterval(smsCountdownTimer.value)
      smsCountdownTimer.value = null
    }
    void refreshCaptcha()
  }

  async function refreshCaptcha() {
    captchaLoading.value = true
    try {
      const result = await authStore.fetchCaptcha()
      if (result) {
        captchaId.value = result.captcha_id
        captchaImage.value = result.captcha_image
      } else {
        notify.error(t('auth.modal.captchaLoadFailed'))
      }
    } catch (error) {
      console.error('Captcha error:', error)
      notify.error(t('auth.modal.captchaNetworkError'))
    } finally {
      captchaLoading.value = false
    }
  }

  watch(
    () => props.visible,
    (newValue) => {
      if (newValue) {
        if (!authStore.isAuthenticated) {
          uiStore.syncGuestLocaleFromBrowser()
        }
        void refreshCaptcha()
        document.body.style.overflow = 'hidden'
      } else {
        document.body.style.overflow = ''
      }
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    document.body.style.overflow = ''
    if (smsCountdownTimer.value) {
      clearInterval(smsCountdownTimer.value)
      smsCountdownTimer.value = null
    }
    if (emailCountdownTimer.value) {
      clearInterval(emailCountdownTimer.value)
      emailCountdownTimer.value = null
    }
  })

  async function handleLogin() {
    if (!loginForm.value.phone || !loginForm.value.password) {
      notify.warning(t('auth.modal.fillAllFields'))
      return
    }

    if (!loginForm.value.captcha || loginForm.value.captcha.length !== 4) {
      notify.warning(t('auth.modal.enter4DigitCaptcha'))
      return
    }

    if (!captchaId.value) {
      notify.warning(t('auth.modal.waitCaptchaLoad'))
      return
    }

    isLoading.value = true

    try {
      const id = loginForm.value.phone.trim()
      const isEmailLogin = id.includes('@')
      const result = await authStore.login(
        isEmailLogin
          ? {
              email: id,
              password: loginForm.value.password,
              captcha: loginForm.value.captcha,
              captcha_id: captchaId.value,
            }
          : {
              phone: id,
              password: loginForm.value.password,
              captcha: loginForm.value.captcha,
              captcha_id: captchaId.value,
            }
      )

      if (result.success) {
        const userName = result.user?.username || ''
        notify.success(
          userName
            ? t('auth.modal.loginWelcome', { name: userName })
            : t('auth.modal.loginSuccessPlain')
        )

        if (authStore.showSessionExpiredModal) {
          emit('success')
        } else {
          setTimeout(() => {
            emit('success')
            closeModal()
          }, 1500)
        }
      } else {
        notify.error(result.message || t('auth.loginFailed'))
        loginForm.value.captcha = ''
        void refreshCaptcha()
      }
    } catch (error) {
      console.error('Login error:', error)
      notify.error(t('auth.modal.networkLoginError'))
      loginForm.value.captcha = ''
      void refreshCaptcha()
    } finally {
      isLoading.value = false
    }
  }

  function startEmailCountdown() {
    emailCountdown.value = 60
    if (emailCountdownTimer.value) {
      clearInterval(emailCountdownTimer.value)
      emailCountdownTimer.value = null
    }
    emailCountdownTimer.value = setInterval(() => {
      emailCountdown.value--
      if (emailCountdown.value <= 0 && emailCountdownTimer.value) {
        clearInterval(emailCountdownTimer.value)
        emailCountdownTimer.value = null
      }
    }, 1000)
  }

  const SIMPLE_EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  async function sendRegisterEmailCode() {
    const email = registerForm.value.registrationEmail.trim()
    if (!email || !showOverseasEmailFlow.value) {
      notify.warning(t('auth.modal.educationEmailInvalid'))
      return
    }
    if (!SIMPLE_EMAIL_RE.test(email)) {
      notify.warning(t('auth.modal.educationEmailInvalid'))
      return
    }
    if (!registerForm.value.captcha || registerForm.value.captcha.length !== 4) {
      notify.warning(t('auth.modal.enterCaptchaFirst'))
      return
    }
    if (!captchaId.value) {
      notify.warning(t('auth.modal.waitCaptchaLoad'))
      return
    }
    if (emailCountdown.value > 0) {
      return
    }

    emailSending.value = true
    try {
      const response = await fetch('/api/auth/email/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          purpose: 'register',
          captcha: registerForm.value.captcha,
          captcha_id: captchaId.value,
        }),
      })
      const data = await response.json().catch(() => ({}))
      if (response.ok) {
        notify.success(t('auth.modal.emailCodeSent'))
        startEmailCountdown()
      } else {
        notify.error(
          typeof data.detail === 'string' ? data.detail : t('auth.modal.emailSendFailed')
        )
        registerForm.value.captcha = ''
        void refreshCaptcha()
      }
    } catch {
      notify.error(t('auth.modal.networkRegisterError'))
      registerForm.value.captcha = ''
      void refreshCaptcha()
    } finally {
      emailSending.value = false
    }
  }

  async function handleRegister() {
    if (registerForm.value.password.length < 8) {
      notify.warning(t('auth.modal.passwordMin8'))
      return
    }

    if (!registerForm.value.captcha || registerForm.value.captcha.length !== 4) {
      notify.warning(t('auth.modal.enter4DigitCaptcha'))
      return
    }

    if (!captchaId.value) {
      notify.warning(t('auth.modal.waitCaptchaLoad'))
      return
    }

    if (registerRegionLoading.value || registerRegion.value === null) {
      notify.warning(t('auth.modal.waitRegionDetection'))
      return
    }

    if (showOverseasEmailFlow.value) {
      const email = registerForm.value.registrationEmail.trim()
      if (!email || !registerForm.value.emailCode || registerForm.value.emailCode.length !== 6) {
        notify.warning(t('auth.modal.fillRequired'))
        return
      }
      if (!registerForm.value.outsideMainlandAcknowledged) {
        notify.warning(t('auth.modal.acknowledgeOverseasRequired'))
        return
      }

      isLoading.value = true
      try {
        const response = await fetch('/api/auth/register-overseas', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            password: registerForm.value.password,
            name: registerForm.value.name,
            email_code: registerForm.value.emailCode,
            captcha: registerForm.value.captcha,
            captcha_id: captchaId.value,
            outside_mainland_acknowledged: true,
          }),
        })
        const data = await response.json().catch(() => ({}))
        if (response.ok) {
          notify.success(t('auth.modal.registerSuccess'))
          switchLoginRegisterTab('login')
          loginForm.value.phone = email
        } else {
          notify.error(
            typeof data.detail === 'string' ? data.detail : t('auth.modal.registerFailed')
          )
          registerForm.value.captcha = ''
          void refreshCaptcha()
        }
      } catch {
        notify.error(t('auth.modal.networkRegisterError'))
        registerForm.value.captcha = ''
        void refreshCaptcha()
      } finally {
        isLoading.value = false
      }
      return
    }

    if (
      !registerForm.value.phone ||
      !registerForm.value.password ||
      !registerForm.value.name ||
      !registerForm.value.invitationCode
    ) {
      notify.warning(t('auth.modal.fillRequired'))
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
        notify.success(t('auth.modal.registerSuccess'))
        switchLoginRegisterTab('login')
        loginForm.value.phone = registerForm.value.phone
      } else {
        notify.error(data.detail || t('auth.modal.registerFailed'))
        registerForm.value.captcha = ''
        void refreshCaptcha()
      }
    } catch (error) {
      console.error('Register error:', error)
      notify.error(t('auth.modal.networkRegisterError'))
      registerForm.value.captcha = ''
      void refreshCaptcha()
    } finally {
      isLoading.value = false
    }
  }

  async function sendSmsCode(type: 'login' | 'reset') {
    const form = type === 'login' ? smsLoginForm.value : forgotForm.value

    if (!form.phone || !form.phone.trim()) {
      notify.warning(t('auth.modal.phone11Digits'))
      return
    }

    if (!form.captcha || form.captcha.length !== 4) {
      notify.warning(t('auth.modal.enterCaptchaFirst'))
      return
    }

    if (!captchaId.value) {
      notify.warning(t('auth.modal.waitCaptchaLoad'))
      return
    }

    const trimmed = form.phone.trim()
    const useEmail = trimmed.includes('@') && (type === 'reset' || type === 'login')

    if (useEmail) {
      if (!SIMPLE_EMAIL_RE.test(trimmed)) {
        notify.warning(t('auth.modal.educationEmailInvalid'))
        return
      }
    } else if (type === 'login' && trimmed.length !== 11) {
      notify.warning(t('auth.modal.phone11Digits'))
      return
    } else if (type === 'reset' && trimmed.length !== 11) {
      notify.warning(t('auth.modal.phone11Digits'))
      return
    }

    smsSending.value = true

    try {
      if (useEmail) {
        const purpose = type === 'login' ? 'login' : 'reset_password'
        const response = await fetch('/api/auth/email/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: trimmed,
            purpose,
            captcha: form.captcha,
            captcha_id: captchaId.value,
          }),
        })
        const data = await response.json().catch(() => ({}))
        if (response.ok) {
          notify.success(t('auth.modal.emailCodeSent'))
          smsSent.value = true
          startCountdown()
        } else {
          notify.error(
            typeof data.detail === 'string' ? data.detail : t('auth.modal.emailSendFailed')
          )
          form.captcha = ''
          void refreshCaptcha()
        }
      } else {
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
          notify.success(t('auth.modal.smsSentSuccess'))
          smsSent.value = true
          startCountdown()
        } else {
          notify.error(data.detail || t('auth.modal.smsSendFailed'))
          form.captcha = ''
          void refreshCaptcha()
        }
      }
    } catch (error) {
      console.error('Verification code send error:', error)
      notify.error(
        useEmail ? t('auth.modal.networkEmailCodeError') : t('auth.modal.networkSmsError')
      )
      form.captcha = ''
      void refreshCaptcha()
    } finally {
      smsSending.value = false
    }
  }

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

  async function handleSmsLogin() {
    if (!smsLoginForm.value.smsCode || smsLoginForm.value.smsCode.length !== 6) {
      notify.warning(
        smsLoginUsesEmail.value
          ? t('auth.modal.enter6DigitEmailCode')
          : t('auth.modal.enter6DigitSms')
      )
      return
    }

    const trimmed = smsLoginForm.value.phone.trim()
    const useEmailOtp = trimmed.includes('@')

    isLoading.value = true

    try {
      const response = useEmailOtp
        ? await fetch('/api/auth/email/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: trimmed,
              email_code: smsLoginForm.value.smsCode,
            }),
          })
        : await fetch('/api/auth/sms/login', {
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
        const token = data.access_token || data.token
        if (token) authStore.setToken(token)
        const userName = data.user?.name || ''
        notify.success(
          userName
            ? t('auth.modal.loginWelcome', { name: userName })
            : t('auth.modal.loginSuccessPlain')
        )

        if (authStore.showSessionExpiredModal) {
          emit('success')
        } else {
          setTimeout(() => {
            emit('success')
            closeModal()
          }, 1500)
        }
      } else {
        notify.error(
          data.detail ||
            (useEmailOtp ? t('auth.modal.emailLoginFailed') : t('auth.modal.smsLoginFailed'))
        )
      }
    } catch (error) {
      console.error('OTP login error:', error)
      notify.error(
        useEmailOtp ? t('auth.modal.networkEmailLoginError') : t('auth.modal.networkSmsLoginError')
      )
    } finally {
      isLoading.value = false
    }
  }

  async function handleResetPassword() {
    if (!forgotForm.value.smsCode || forgotForm.value.smsCode.length !== 6) {
      notify.warning(
        forgotUsesEmail.value
          ? t('auth.modal.enter6DigitEmailCode')
          : t('auth.modal.enter6DigitSms')
      )
      return
    }

    if (!forgotForm.value.newPassword || forgotForm.value.newPassword.length < 8) {
      notify.warning(t('auth.modal.passwordMin8'))
      return
    }

    if (forgotForm.value.newPassword !== forgotForm.value.confirmPassword) {
      notify.warning(t('auth.modal.passwordMismatch'))
      return
    }

    isLoading.value = true

    try {
      const trimmed = forgotForm.value.phone.trim()
      const useEmail = trimmed.includes('@')

      const response = useEmail
        ? await fetch('/api/auth/reset-password-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: trimmed,
              email_code: forgotForm.value.smsCode,
              new_password: forgotForm.value.newPassword,
            }),
          })
        : await fetch('/api/auth/reset-password', {
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
        notify.success(t('auth.modal.resetSuccess'))
        backToLogin()
        loginForm.value.phone = trimmed
      } else {
        notify.error(data.detail || t('auth.modal.resetFailed'))
      }
    } catch (error) {
      console.error('Reset password error:', error)
      notify.error(t('auth.modal.networkResetError'))
    } finally {
      isLoading.value = false
    }
  }

  function handleBackdropClick() {
    if (props.persistent) {
      return
    }
    closeModal()
  }

  return {
    authStore,
    t,
    currentView,
    activeTab,
    loginForm,
    registerForm,
    smsLoginForm,
    forgotForm,
    captchaId,
    captchaImage,
    captchaLoading,
    smsSending,
    smsCountdown,
    smsSent,
    emailSending,
    emailCountdown,
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
    handleResetPassword,
    handleBackdropClick,
  }
}
