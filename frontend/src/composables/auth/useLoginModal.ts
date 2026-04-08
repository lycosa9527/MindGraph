/**
 * State and handlers for LoginModal (login, register, SMS, forgot password).
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore, useUIStore } from '@/stores'

export type LoginModalViewState = 'login' | 'register' | 'sms-login' | 'forgot-password'

type LoginModalEmit = {
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}

export function useLoginModal(
  props: { visible: boolean; persistent?: boolean },
  emit: LoginModalEmit,
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

  const isOverseasRegister = computed(() => {
    const e = registerForm.value.registrationEmail.trim()
    return e.includes('@') && /\.[a-z0-9-]+$/i.test(e.split('@')[1] ?? '')
  })

  const forgotUsesEmail = computed(() => {
    const id = forgotForm.value.phone.trim()
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
    return currentView.value === 'sms-login' ? t('auth.smsLogin') : t('auth.resetPassword')
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

  watch(isOverseasRegister, (on) => {
    if (on) {
      registerForm.value.phone = ''
      registerForm.value.invitationCode = ''
      if (uiStore.language === 'zh') {
        uiStore.setLanguage('en')
      }
    } else {
      registerForm.value.emailCode = ''
      registerForm.value.outsideMainlandAcknowledged = false
    }
  })

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
        if (authStore.showSessionExpiredModal) {
          document.body.style.overflow = 'hidden'
        }
      } else {
        document.body.style.overflow = ''
      }
    },
    { immediate: true }
  )

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

  async function sendRegisterEmailCode() {
    const email = registerForm.value.registrationEmail.trim()
    if (!email || !isOverseasRegister.value) {
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

    if (isOverseasRegister.value) {
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
    const useEmail = type === 'reset' && trimmed.includes('@')

    if (type === 'login' && trimmed.length !== 11) {
      notify.warning(t('auth.modal.phone11Digits'))
      return
    }

    if (useEmail) {
      const simple = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!simple.test(trimmed)) {
        notify.warning(t('auth.modal.educationEmailInvalid'))
        return
      }
    } else if (type === 'reset' && trimmed.length !== 11) {
      notify.warning(t('auth.modal.phone11Digits'))
      return
    }

    smsSending.value = true

    try {
      if (useEmail) {
        const response = await fetch('/api/auth/email/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: trimmed,
            purpose: 'reset_password',
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
      console.error('SMS error:', error)
      notify.error(t('auth.modal.networkSmsError'))
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
      notify.warning(t('auth.modal.enter6DigitSms'))
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
        notify.error(data.detail || t('auth.modal.smsLoginFailed'))
      }
    } catch (error) {
      console.error('SMS login error:', error)
      notify.error(t('auth.modal.networkSmsLoginError'))
    } finally {
      isLoading.value = false
    }
  }

  async function handleResetPassword() {
    if (!forgotForm.value.smsCode || forgotForm.value.smsCode.length !== 6) {
      notify.warning(t('auth.modal.enter6DigitSms'))
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

  function handleBackdropClick(event: MouseEvent) {
    if (props.persistent) {
      return
    }
    if (event.target === event.currentTarget) {
      closeModal()
    }
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
    isOverseasRegister,
    forgotUsesEmail,
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
