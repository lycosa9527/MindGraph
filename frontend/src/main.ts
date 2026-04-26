/**
 * MindGraph Vue 3 Application Entry Point
 */
import { createApp } from 'vue'

import { createPinia } from 'pinia'

import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/message-box/style/css'
// Element Plus programmatic-API styles (not auto-resolved by unplugin)
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/notification/style/css'

import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import { eventBus } from './composables/core/useEventBus'
import './fonts/eagerFonts'
import { i18n, loadLocaleMessages, setI18nLocale } from './i18n'
import router from './router'
import { useDiagramStore } from './stores/diagram'
import { useUIStore } from './stores/ui'
// Styles
import './styles/index.css'

async function bootstrap(): Promise<void> {
  const app = createApp(App)

  const pinia = createPinia()
  app.use(pinia)

  eventBus.on('diagram:layout_recalc_bump', () => {
    useDiagramStore().layoutRecalcTrigger += 1
  })

  const uiStore = useUIStore()
  await loadLocaleMessages(uiStore.language)
  setI18nLocale(uiStore.language)

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
