/**
 * Vue Router Configuration
 */
import {
  type RouteRecordRaw,
  createRouter,
  createWebHistory,
} from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'

const routes: RouteRecordRaw[] = [
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
  {
    path: '/',
    name: 'Main',
    redirect: '/mindmate',
  },
  {
    path: '/mindmate',
    name: 'MindMate',
    component: () => import('@/pages/MindMatePage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/mindgraph',
    name: 'MindGraph',
    component: () => import('@/pages/MindGraphPage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/canvas',
    name: 'Canvas',
    component: () => import('@/pages/CanvasPage.vue'),
    meta: { requiresAuth: true, layout: 'canvas' },
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
    path: '/template',
    name: 'Template',
    component: () => import('@/pages/TemplatePage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/course',
    name: 'Course',
    component: () => import('@/pages/CoursePage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/community',
    name: 'Community',
    component: () => import('@/pages/CommunityPage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/school-zone',
    name: 'SchoolZone',
    component: () => import('@/pages/SchoolZonePage.vue'),
    meta: { requiresAuth: true, requiresOrganization: true, layout: 'main' },
  },
  {
    path: '/askonce',
    name: 'AskOnce',
    component: () => import('@/pages/AskOncePage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/debateverse',
    name: 'DebateVerse',
    component: () => import('@/pages/DebateVersePage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/knowledge-space',
    name: 'KnowledgeSpace',
    component: () => import('@/pages/KnowledgeSpacePage.vue'),
    meta: { requiresAuth: true, layout: 'main' },
  },
  {
    path: '/chunk-test',
    name: 'ChunkTest',
    component: () => import('@/pages/ChunkTestPage.vue'),
    meta: {
      requiresAuth: true,
      requiresFeatureFlag: 'ragChunkTest',
      layout: 'main',
    },
  },
  {
    path: '/chunk-test/results/:testId',
    name: 'ChunkTestResults',
    component: () => import('@/pages/ChunkTestResultsPage.vue'),
    meta: {
      requiresAuth: true,
      requiresFeatureFlag: 'ragChunkTest',
      layout: 'main',
    },
  },
  {
    path: '/library',
    name: 'Library',
    component: () => import('@/pages/LibraryPage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/library/:id',
    name: 'LibraryViewer',
    component: () => import('@/pages/LibraryViewerPage.vue'),
    meta: { layout: 'main' },
  },
  {
    path: '/library/bookmark/:uuid',
    name: 'LibraryBookmark',
    component: () => import('@/pages/LibraryBookmarkPage.vue'),
    meta: { layout: 'main', requiresAuth: true },
  },
  {
    path: '/gewe',
    name: 'Gewe',
    component: () => import('@/pages/GewePage.vue'),
    meta: {
      layout: 'main',
      requiresAuth: true,
      requiresAdmin: true,
    },
  },
  {
    path: '/teacher-usage',
    name: 'TeacherUsage',
    component: () => import('@/pages/TeacherUsagePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
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
  const featureFlagsStore = useFeatureFlagsStore()

  // Fetch feature flags if needed (for router guard - doesn't use vue-query)
  // Fetch for: routes with feature flag checks, OR any main layout route (sidebar needs flags)
  const needsFeatureFlags =
    to.meta.requiresFeatureFlag ||
    to.meta.layout === 'main' ||
    to.name === 'Course' ||
    to.name === 'Template' ||
    to.name === 'Community' ||
    to.name === 'AskOnce' ||
    to.name === 'DebateVerse' ||
    to.name === 'SchoolZone' ||
    to.name === 'KnowledgeSpace' ||
    to.name === 'Library' ||
    to.name === 'SmartResponse' ||
    to.name === 'TeacherUsage'
  if (needsFeatureFlags) {
    await featureFlagsStore.fetchFlags()
  }

  // Check authentication status - only for protected routes
  // checkAuth() is smart: it uses cached user if available, only makes API call if needed
  if (to.meta.requiresAuth) {
    // Check if user was previously authenticated (before checkAuth clears it)
    const hadUserBeforeCheck =
      !!authStore.user || !!sessionStorage.getItem('auth_user')

    const isAuthenticated = await authStore.checkAuth()
    if (!isAuthenticated) {
      // If user existed before checkAuth but checkAuth failed, session expired
      if (hadUserBeforeCheck && to.name !== 'Login') {
        // Session expired - show modal overlay and prevent navigation
        // Stay on current page (from) instead of navigating to protected route
        authStore.handleTokenExpired(undefined, undefined) // undefined = stay on current page
        // Prevent navigation - user must login first
        return next(false)
      }

      // User was never authenticated - show login modal with redirect path
      authStore.handleTokenExpired(undefined, to.fullPath)
      // Prevent navigation - user must login first
      return next(false)
    }
  }

  // Check admin access (admin-only, not managers)
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return next({ name: 'MindMate' })
  }

  // Check organization membership for school zone
  if (to.meta.requiresOrganization && !authStore.user?.schoolId) {
    return next({ name: 'MindMate' })
  }

  // Check feature flags
  if (
    to.meta.requiresFeatureFlag === 'ragChunkTest' &&
    !featureFlagsStore.getFeatureRagChunkTest()
  ) {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Course' && !featureFlagsStore.getFeatureCourse()) {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Template' && !featureFlagsStore.getFeatureTemplate()) {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Community' && !featureFlagsStore.getFeatureCommunity()) {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'AskOnce' && !featureFlagsStore.getFeatureAskOnce()) {
    return next({ name: 'MindMate' })
  }
  if (
    to.name === 'DebateVerse' &&
    !featureFlagsStore.getFeatureDebateverse()
  ) {
    return next({ name: 'MindMate' })
  }
  if (
    to.name === 'SchoolZone' &&
    !featureFlagsStore.getFeatureSchoolZone()
  ) {
    return next({ name: 'MindMate' })
  }
  if (
    to.name === 'KnowledgeSpace' &&
    !featureFlagsStore.getFeatureKnowledgeSpace()
  ) {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Library' && !featureFlagsStore.getFeatureLibrary()) {
    return next({ name: 'MindMate' })
  }
  if (
    to.name === 'SmartResponse' &&
    !featureFlagsStore.getFeatureSmartResponse()
  ) {
    return next({ name: 'MindMate' })
  }
  if (
    to.name === 'TeacherUsage' &&
    !featureFlagsStore.getFeatureTeacherUsage()
  ) {
    return next({ name: 'MindMate' })
  }

  // Redirect authenticated users away from guest-only pages
  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return next({ name: 'MindMate' })
  }

  next()
})

export default router
