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

export function useLoginModal(props: { visible: boolean }, emit: LoginModalEmit) {
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
    phone: '',
    password: '',
    name: '',
    invitationCode: '',
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
      const result = await authStore.login({
        phone: loginForm.value.phone,
        password: loginForm.value.password,
        captcha: loginForm.value.captcha,
        captcha_id: captchaId.value,
      })

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

  async function handleRegister() {
    if (
      !registerForm.value.phone ||
      !registerForm.value.password ||
      !registerForm.value.name ||
      !registerForm.value.invitationCode
    ) {
      notify.warning(t('auth.modal.fillRequired'))
      return
    }

    if (registerForm.value.password.length < 8) {
      notify.warning(t('auth.modal.passwordMin8'))
      return
    }

    if (!registerForm.value.captcha || registerForm.value.captcha.length !== 4) {
      notify.warning(t('auth.modal.enter4DigitCaptcha'))
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

    if (!form.phone || form.phone.length !== 11) {
      notify.warning(t('auth.modal.phone11Digits'))
      return
    }

    if (!form.captcha || form.captcha.length !== 4) {
      notify.warning(t('auth.modal.enterCaptchaFirst'))
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
        notify.success(t('auth.modal.smsSentSuccess'))
        smsSent.value = true
        startCountdown()
      } else {
        notify.error(data.detail || t('auth.modal.smsSendFailed'))
        form.captcha = ''
        void refreshCaptcha()
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
        notify.success(t('auth.modal.resetSuccess'))
        backToLogin()
        loginForm.value.phone = forgotForm.value.phone
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
  }
}
