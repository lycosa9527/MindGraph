import { createApp, defineComponent, h, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { createPinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTrainingBuilderSidebar } from '@/composables/training/useTrainingBuilderSidebar'
import { useUIStore } from '@/stores/ui'

function builderRoutes() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/training', component: { template: '<div />' } },
      { path: '/training/builder', component: { template: '<div />' } },
      { path: '/training/builder/:courseId', component: { template: '<div />' } },
      { path: '/mindmate', component: { template: '<div />' } },
    ],
  })
}

async function mountAt(path: string) {
  const pinia = createPinia()
  const ui = useUIStore(pinia)
  const router = builderRoutes()
  await router.push(path)
  await router.isReady()
  const host = document.createElement('div')
  const app = createApp(
    defineComponent({
      setup() {
        useTrainingBuilderSidebar()
        return () => h('div')
      },
    })
  )
  app.use(pinia)
  app.use(router)
  app.mount(host)
  return { app, router, ui }
}

describe('useTrainingBuilderSidebar', () => {
  const apps: ReturnType<typeof createApp>[] = []

  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }))
    )
  })

  afterEach(() => {
    for (const app of apps) app.unmount()
    apps.length = 0
  })

  it('collapses on entry and restores the previous state on leave', async () => {
    const { app, router, ui } = await mountAt('/training')
    apps.push(app)
    ui.setSidebarCollapsed(false)

    await router.push('/training/builder')
    await nextTick()
    expect(ui.sidebarCollapsed).toBe(true)

    await router.push('/training/builder/course-1')
    await nextTick()
    expect(ui.sidebarCollapsed).toBe(true)

    ui.setSidebarCollapsed(false)
    await router.push('/mindmate')
    await nextTick()
    expect(ui.sidebarCollapsed).toBe(false)
  })

  it('restores a sidebar that was already collapsed', async () => {
    const { app, router, ui } = await mountAt('/training')
    apps.push(app)
    ui.setSidebarCollapsed(true)

    await router.push('/training/builder')
    await nextTick()
    ui.setSidebarCollapsed(false)

    await router.push('/training')
    await nextTick()
    expect(ui.sidebarCollapsed).toBe(true)
  })

  it('restores the sidebar when the layout unmounts inside the builder', async () => {
    const { app, ui } = await mountAt('/training/builder')
    expect(ui.sidebarCollapsed).toBe(true)
    app.unmount()
    expect(ui.sidebarCollapsed).toBe(false)
  })
})
