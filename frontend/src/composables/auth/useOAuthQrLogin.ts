/**
 * OAuth QR login: load SDKs, fetch providers, render WxLogin / DTFrameLogin.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useAuthStore } from '@/stores'
import { notifyOAuthError } from '@/utils/oauthLoginUi'
import apiClient from '@/utils/apiClient'

export type OAuthProvider = 'wechat' | 'dingtalk'
export type OAuthQrMode = 'login' | 'bind'

export interface OAuthProvidersPayload {
  organization_id: number
  wechat_enabled: boolean
  dingtalk_enabled: boolean
  wechat_app_id: string
  dingtalk_client_id: string
  dingtalk_scope: string
  wechat_redirect_uri: string
  dingtalk_redirect_uri: string
}

declare global {
  interface Window {
    WxLogin?: new (opts: Record<string, unknown>) => void
    DTFrameLogin?: (
      frame: Record<string, unknown>,
      params: Record<string, unknown>,
      success: (result: { authCode?: string; redirectUrl?: string; state?: string }) => void,
      error: (msg: string) => void
    ) => void
  }
}

const WX_SCRIPT = 'https://res.wx.qq.com/connect/zh_CN/htmledition/js/wxLogin.js'
const DD_SCRIPT = 'https://g.alicdn.com/dingding/h5-dingtalk-login/0.21.0/ddlogin.js'

function loadScript(src: string, id: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.getElementById(id)) {
      resolve()
      return
    }
    const el = document.createElement('script')
    el.id = id
    el.src = src
    el.async = true
    el.onload = () => resolve()
    el.onerror = () => reject(new Error(`script_load_failed:${src}`))
    document.head.appendChild(el)
  })
}

export function useOAuthQrLogin(options: {
  inviteCode: () => string
  mode: () => OAuthQrMode
  activeProvider: () => OAuthProvider
  onSuccess?: () => void
}) {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()

  const providers = ref<OAuthProvidersPayload | null>(null)
  const loadingProviders = ref(false)
  const providerError = ref('')
  const activeTab = ref<OAuthProvider>('wechat')
  const wechatContainerId = 'mg-oauth-wechat-qr'
  const dingtalkContainerId = 'mg-oauth-dingtalk-qr'

  const invite = computed(() => (options.inviteCode() || '').trim().toUpperCase())
  const isBindMode = computed(() => options.mode() === 'bind')

  async function fetchProvidersFromLinks(): Promise<boolean> {
    const res = await apiClient.get('/api/auth/oauth/links')
    if (!res.ok) {
      return false
    }
    const data = (await res.json()) as {
      wechat_login_enabled?: boolean
      dingtalk_login_enabled?: boolean
    }
    providers.value = {
      organization_id: 0,
      wechat_enabled: data.wechat_login_enabled === true,
      dingtalk_enabled: data.dingtalk_login_enabled === true,
      wechat_app_id: '',
      dingtalk_client_id: '',
      dingtalk_scope: 'openid',
      wechat_redirect_uri: '',
      dingtalk_redirect_uri: '',
    }
    if (providers.value.wechat_enabled) {
      activeTab.value = 'wechat'
    } else if (providers.value.dingtalk_enabled) {
      activeTab.value = 'dingtalk'
    }
    return true
  }

  async function fetchProviders(): Promise<void> {
    providerError.value = ''
    providers.value = null
    loadingProviders.value = true
    try {
      if (isBindMode.value) {
        const ok = await fetchProvidersFromLinks()
        if (!ok) {
          providerError.value = 'providers_failed'
        }
        return
      }
      if (!invite.value) {
        providerError.value = 'invite_required'
        return
      }
      const res = await apiClient.get(
        `/api/auth/oauth/providers?invite=${encodeURIComponent(invite.value)}`
      )
      if (!res.ok) {
        providerError.value = 'providers_failed'
        return
      }
      providers.value = (await res.json()) as OAuthProvidersPayload
      if (providers.value.wechat_enabled) {
        activeTab.value = 'wechat'
      } else if (providers.value.dingtalk_enabled) {
        activeTab.value = 'dingtalk'
      }
    } catch {
      providerError.value = 'providers_failed'
    } finally {
      loadingProviders.value = false
    }
  }

  function notifySuccess(): void {
    if (!isBindMode.value) {
      eventBus.emit('auth:login_success', {})
    }
    notify.success(
      isBindMode.value ? t('auth.oauthBindSuccess') : t('auth.qrLoginSuccess')
    )
    options.onSuccess?.()
  }

  async function startWechatWidget(state: string, appId: string, redirectUri: string): Promise<void> {
    await loadScript(WX_SCRIPT, 'mg-wx-login-js')
    const el = document.getElementById(wechatContainerId)
    if (!el || !window.WxLogin) {
      notify.error(t('auth.qrLoginStartFailed'))
      return
    }
    el.innerHTML = ''
    new window.WxLogin({
      self_redirect: true,
      id: wechatContainerId,
      appid: appId,
      scope: 'snsapi_login',
      redirect_uri: redirectUri,
      state,
      stylelite: 1,
    })
  }

  async function startDingtalkWidget(
    state: string,
    clientId: string,
    redirectUri: string,
    scope: string
  ): Promise<void> {
    await loadScript(DD_SCRIPT, 'mg-dd-login-js')
    const el = document.getElementById(dingtalkContainerId)
    if (!el || !window.DTFrameLogin) {
      notify.error(t('auth.qrLoginStartFailed'))
      return
    }
    el.innerHTML = ''
    window.DTFrameLogin(
      { id: dingtalkContainerId, width: 300, height: 300 },
      {
        redirect_uri: redirectUri,
        client_id: clientId,
        scope,
        response_type: 'code',
        state,
        prompt: 'consent',
      },
      async (loginResult) => {
        const authCode = loginResult.authCode
        const st = loginResult.state || state
        if (!authCode) {
          notify.error(t('auth.qrLoginExchangeFailed'))
          return
        }
        const path = isBindMode.value
          ? '/api/auth/oauth/dingtalk/bind/complete'
          : '/api/auth/oauth/dingtalk/complete'
        try {
          const res = await apiClient.post(path, { authCode, state: st })
          if (!res.ok) {
            const err = await res.json().catch(() => ({}))
            const detail = typeof err.detail === 'string' ? err.detail : ''
            notifyOAuthError(detail || 'oauth_exchange_failed', notify, t)
            return
          }
          if (!isBindMode.value) {
            await authStore.checkAuth()
          }
          notifySuccess()
        } catch {
          notify.error(t('auth.qrLoginExchangeFailed'))
        }
      },
      (errorMsg) => {
        notify.error(errorMsg || t('auth.qrLoginExchangeFailed'))
      }
    )
  }

  async function mountActiveProvider(): Promise<void> {
    if (!providers.value) {
      return
    }
    if (!isBindMode.value && !invite.value) {
      return
    }
    const prov = options.activeProvider()
    if (prov === 'wechat' && providers.value.wechat_enabled) {
      const startPath = isBindMode.value
        ? '/api/auth/oauth/wechat/bind/start'
        : `/api/auth/oauth/wechat/start?invite=${encodeURIComponent(invite.value)}`
      const res = await apiClient.get(startPath)
      if (!res.ok) {
        notify.error(t('auth.qrLoginStartFailed'))
        return
      }
      const data = (await res.json()) as {
        state: string
        appId: string
        redirectUri: string
      }
      try {
        await startWechatWidget(data.state, data.appId, data.redirectUri)
      } catch {
        notify.error(t('auth.qrLoginStartFailed'))
      }
    }
    if (prov === 'dingtalk' && providers.value.dingtalk_enabled) {
      const startPath = isBindMode.value
        ? '/api/auth/oauth/dingtalk/bind/start'
        : `/api/auth/oauth/dingtalk/start?invite=${encodeURIComponent(invite.value)}`
      const res = await apiClient.get(startPath)
      if (!res.ok) {
        notify.error(t('auth.qrLoginStartFailed'))
        return
      }
      const data = (await res.json()) as {
        state: string
        clientId: string
        redirectUri: string
        scope: string
      }
      try {
        await startDingtalkWidget(
          data.state,
          data.clientId,
          data.redirectUri,
          data.scope || 'openid'
        )
      } catch {
        notify.error(t('auth.qrLoginStartFailed'))
      }
    }
  }

  watch(
    () => [invite.value, options.activeProvider(), options.mode()],
    () => {
      void fetchProviders().then(() => mountActiveProvider())
    },
    { immediate: true }
  )

  onBeforeUnmount(() => {
    const w = document.getElementById(wechatContainerId)
    const d = document.getElementById(dingtalkContainerId)
    if (w) {
      w.innerHTML = ''
    }
    if (d) {
      d.innerHTML = ''
    }
  })

  return {
    providers,
    loadingProviders,
    providerError,
    activeTab,
    wechatContainerId,
    dingtalkContainerId,
    fetchProviders,
    mountActiveProvider,
  }
}
