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
import './fonts/eagerFonts'
import { i18n, loadLocaleMessages, setI18nLocale } from './i18n'
import router from './router'
import { useUIStore } from './stores/ui'
// Styles
import './styles/index.css'

async function bootstrap(): Promise<void> {
  const app = createApp(App)

  const pinia = createPinia()
  app.use(pinia)

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

  app.mount('#app')
}

void bootstrap()
