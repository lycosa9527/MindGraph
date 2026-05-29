/**
 * MindGraph Vue 3 Application Entry Point
 */
import { createApp } from 'vue'

import { createPinia } from 'pinia'

import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import './fonts/eagerFonts'
import { ensureElementPlusProgrammaticStyles } from '@/composables/core/notifications'
import { preloadMarkdownRendererForRoute } from '@/composables/core/useMarkdown'
import { i18n, htmlLangForLocale, loadLocaleMessages, setI18nLocale } from './i18n'
import router from './router'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from './stores/ui'
import { isUiLocale } from './i18n/locales'
// Styles
import './styles/index.css'

async function bootstrap(): Promise<void> {
  const app = createApp(App)

  const pinia = createPinia()
  app.use(pinia)

  const authStore = useAuthStore()
  const uiStore = useUIStore()

  const bootstrapLang =
    authStore.user?.uiLanguage && isUiLocale(authStore.user.uiLanguage)
      ? authStore.user.uiLanguage
      : uiStore.language

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
  app.use(VueQueryPlugin, { queryClient })

  app.config.errorHandler = (err, instance, info) => {
    console.error('Vue Error:', err)
    console.error('Component:', instance)
    console.error('Info:', info)
  }

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
