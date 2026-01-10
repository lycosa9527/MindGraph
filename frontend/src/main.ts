/**
 * MindGraph Vue 3 Application Entry Point
 */
import { createApp } from 'vue'

import { createPinia } from 'pinia'

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import router from './router'
// Styles
import './styles/index.css'

// Create Vue app
const app = createApp(App)

// Install Pinia
const pinia = createPinia()
app.use(pinia)

// Install Router
app.use(router)

// Install Vue Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute default
      gcTime: 30 * 60 * 1000, // Keep unused data 30 min
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
app.use(VueQueryPlugin, { queryClient })

// Install Element Plus
app.use(ElementPlus)

// Register all Element Plus icons globally
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// Global error handler
app.config.errorHandler = (err, instance, info) => {
  console.error('Vue Error:', err)
  console.error('Component:', instance)
  console.error('Info:', info)
}

// Mount app
app.mount('#app')
