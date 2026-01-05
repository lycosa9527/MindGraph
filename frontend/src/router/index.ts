/**
 * Vue Router Configuration
 */
import { type RouteRecordRaw, createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Main',
    component: () => import('@/pages/MainPage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/canvas',
    name: 'Canvas',
    component: () => import('@/pages/CanvasPage.vue'),
    meta: { requiresAuth: true, layout: 'canvas' },
  },
  {
    path: '/editor',
    name: 'Editor',
    component: () => import('@/pages/EditorPage.vue'),
    meta: { requiresAuth: true, layout: 'editor' },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/pages/AdminPage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'admin' },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { layout: 'auth', guestOnly: true },
  },
  {
    path: '/auth',
    name: 'Auth',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { layout: 'auth', guestOnly: true },
  },
  {
    path: '/demo',
    name: 'DemoLogin',
    component: () => import('@/pages/DemoLoginPage.vue'),
    meta: { layout: 'auth', guestOnly: true },
  },
  {
    path: '/dashboard',
    name: 'PublicDashboard',
    component: () => import('@/pages/PublicDashboardPage.vue'),
    meta: { layout: 'default' },
  },
  {
    path: '/dashboard/login',
    name: 'DashboardLogin',
    component: () => import('@/pages/DashboardLoginPage.vue'),
    meta: { layout: 'auth' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { layout: 'default' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guards
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  // Check authentication status
  if (to.meta.requiresAuth) {
    const isAuthenticated = await authStore.checkAuth()
    if (!isAuthenticated) {
      return next({ name: 'Login', query: { redirect: to.fullPath } })
    }
  }

  // Check admin access
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return next({ name: 'Main' })
  }

  // Redirect authenticated users away from guest-only pages
  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return next({ name: 'Main' })
  }

  next()
})

export default router
