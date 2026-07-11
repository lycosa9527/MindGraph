/**
 * MindGraph Vue 3 Application Entry Point
 */
import { createApp } from 'vue'

import { createPinia } from 'pinia'

import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { registerSW } from 'virtual:pwa-register'

import { ensureElementPlusProgrammaticStyles } from '@/composables/core/notifications'
import { preloadMarkdownRendererForRoute } from '@/composables/core/useMarkdown'
import { useAuthStore } from '@/stores/auth'

import App from './App.vue'
import './fonts/eagerFonts'
import { htmlLangForLocale, i18n, loadLocaleMessages, setI18nLocale } from './i18n'
import type { LocaleCode } from './i18n/locales'
import { isUiLocale } from './i18n/locales'
import router from './router'
import { useUIStore } from './stores/ui'
// Styles
import './styles/index.css'
import { setAppQueryClient } from './utils/appQueryClient'
import { isGuestAuthPath } from './utils/authRedirect'
import { installCsrfFetchInterceptor } from './utils/installCsrfFetchInterceptor'
import { installFrontendErrorReporting } from './utils/installFrontendErrorReporting'
import { bindPwaInstallListeners } from './utils/pwaInstall'
import { reloadForStaleChunk } from './utils/staleChunkReload'

// Attach X-CSRF-Token to same-origin mutations before any request is made.
installCsrfFetchInterceptor()

const pwaDevEnabled = import.meta.env.VITE_PWA_DEV === '1'

if (import.meta.env.PROD || pwaDevEnabled) {
  registerSW({
    immediate: true,
    onNeedRefresh() {
      window.location.reload()
    },
  })
}
bindPwaInstallListeners()

async function bootstrap(): Promise<void> {
  const app = createApp(App)

  const pinia = createPinia()
  app.use(pinia)

  const authStore = useAuthStore()
  const uiStore = useUIStore()

  let bootstrapLang: LocaleCode
  if (authStore.user?.uiLanguage && isUiLocale(authStore.user.uiLanguage)) {
    bootstrapLang = authStore.user.uiLanguage
  } else if (typeof window !== 'undefined' && isGuestAuthPath(window.location.pathname)) {
    uiStore.syncGuestLocaleFromBrowser()
    bootstrapLang = uiStore.language
  } else {
    bootstrapLang = uiStore.language
  }

  await loadLocaleMessages(bootstrapLang)
  setI18nLocale(bootstrapLang)
  if (uiStore.language !== bootstrapLang) {
    uiStore.language = bootstrapLang
    document.documentElement.lang = htmlLangForLocale(bootstrapLang)
  }

  app.use(i18n)

  // Install Router
  app.use(router)

  // Install Vue Query
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        gcTime: 30 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  })
  setAppQueryClient(queryClient)
  app.use(VueQueryPlugin, { queryClient })

  installFrontendErrorReporting(app)

  router.onError((error) => {
    reloadForStaleChunk(error)
  })

  // Avoid flashing DefaultLayout on `/` before the guard redirects (e.g. to `/mindmate`).
  await router.isReady()
  await ensureElementPlusProgrammaticStyles()
  preloadMarkdownRendererForRoute(router.currentRoute.value.path)
  app.mount('#app')
}

function showBootstrapFailureFallback(error: unknown): void {
  console.error('[bootstrap] Failed to start application:', error)
  const root = document.getElementById('app')
  if (!root) {
    return
  }
  root.innerHTML = ''
  const wrap = document.createElement('div')
  wrap.setAttribute(
    'style',
    'font-family:system-ui,sans-serif;max-width:28rem;margin:3rem auto;padding:0 1rem;line-height:1.5;color:#1c1917'
  )
  const title = document.createElement('p')
  title.textContent = 'The app could not start. Check your connection and try again.'
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.textContent = 'Reload'
  btn.setAttribute(
    'style',
    'margin-top:1rem;padding:0.5rem 1rem;cursor:pointer;font:inherit;border:1px solid #78716c;border-radius:6px;background:#fafaf9'
  )
  btn.addEventListener('click', () => {
    window.location.reload()
  })
  wrap.appendChild(title)
  wrap.appendChild(btn)
  root.appendChild(wrap)
}

void bootstrap().catch(showBootstrapFailureFallback)
