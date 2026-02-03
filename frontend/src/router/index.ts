/**
 * Vue Router Configuration
 */
import 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { type RouteRecordRaw, createRouter, createWebHistory } from 'vue-router'

import 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { useAuthStore } from '@/stores/auth'
import 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { useFeatureFlagsStore } from '@/stores/featureFlags'

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
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/mindmate',
    name: 'MindMate',
    component: () => import('@/pages/MindMatePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/mindgraph',
    name: 'MindGraph',
    component: () => import('@/pages/MindGraphPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/canvas',
    name: 'Canvas',
    component: () => import('@/pages/CanvasPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { requiresAuth: true, layout: 'canvas' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/pages/AdminPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { requiresAuth: true, requiresAdmin: true, layout: 'admin' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'auth', guestOnly: true },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/auth',
    name: 'Auth',
    component: () => import('@/pages/LoginPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'auth', guestOnly: true },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/demo',
    name: 'DemoLogin',
    component: () => import('@/pages/DemoLoginPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'auth', guestOnly: true },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/template',
    name: 'Template',
    component: () => import('@/pages/TemplatePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/course',
    name: 'Course',
    component: () => import('@/pages/CoursePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/community',
    name: 'Community',
    component: () => import('@/pages/CommunityPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/school-zone',
    name: 'SchoolZone',
    component: () => import('@/pages/SchoolZonePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { requiresAuth: true, requiresOrganization: true, layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/askonce',
    name: 'AskOnce',
    component: () => import('@/pages/AskOncePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/debateverse',
    name: 'DebateVerse',
    component: () => import('@/pages/DebateVersePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/knowledge-space',
    name: 'KnowledgeSpace',
    component: () => import('@/pages/KnowledgeSpacePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { requiresAuth: true, layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/chunk-test',
    name: 'ChunkTest',
    component: () => import('@/pages/ChunkTestPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { requiresAuth: true, requiresFeatureFlag: 'ragChunkTest', layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/chunk-test/results/:testId',
    name: 'ChunkTestResults',
    component: () => import('@/pages/ChunkTestResultsPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { requiresAuth: true, requiresFeatureFlag: 'ragChunkTest', layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/library',
    name: 'Library',
    component: () => import('@/pages/LibraryPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/library/:id',
    name: 'LibraryViewer',
    component: () => import('@/pages/LibraryViewerPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/library/bookmark/:uuid',
    name: 'LibraryBookmark',
    component: () => import('@/pages/LibraryBookmarkPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main', requiresAuth: true },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/gewe',
    name: 'Gewe',
    component: () => import('@/pages/GewePage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'main', requiresAuth: true, requiresAdmin: true },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/dashboard',
    name: 'PublicDashboard',
    component: () => import('@/pages/PublicDashboardPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'default' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/dashboard/login',
    name: 'DashboardLogin',
    component: () => import('@/pages/DashboardLoginPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'auth' },
  },
  
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },

  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 { layout: 'default' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guards
router.beforeEach(async (to, _from, next) => 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
  const authStore = useAuthStore()
  const featureFlagsStore = useFeatureFlagsStore()
  
  // Fetch feature flags if needed (for router guard - doesn't use vue-query)
  // Fetch flags for any route that might need feature flag checks
  if (to.meta.requiresFeatureFlag ||
      to.name === 'Course' ||
      to.name === 'Template' ||
      to.name === 'Community' ||
      to.name === 'AskOnce' ||
      to.name === 'DebateVerse' ||
      to.name === 'SchoolZone' ||
      to.name === 'KnowledgeSpace' ||
      to.name === 'Library') 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    await featureFlagsStore.fetchFlags()
  }

  // Check authentication status - only for protected routes
  // checkAuth() is smart: it uses cached user if available, only makes API call if needed
  if (to.meta.requiresAuth) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    // Check if user was previously authenticated (before checkAuth clears it)
    const hadUserBeforeCheck = !!authStore.user || !!sessionStorage.getItem('auth_user')
    
    const isAuthenticated = await authStore.checkAuth()
    if (!isAuthenticated) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
      // If user existed before checkAuth but checkAuth failed, session expired
      if (hadUserBeforeCheck && to.name !== 'Login') 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
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
  if (to.meta.requiresAdmin && !authStore.isAdmin) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }

  // Check organization membership for school zone
  if (to.meta.requiresOrganization && !authStore.user?.schoolId) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }

  // Check feature flags
  if (to.meta.requiresFeatureFlag === 'ragChunkTest' && !featureFlagsStore.getFeatureRagChunkTest()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Course' && !featureFlagsStore.getFeatureCourse()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Template' && !featureFlagsStore.getFeatureTemplate()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Community' && !featureFlagsStore.getFeatureCommunity()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'AskOnce' && !featureFlagsStore.getFeatureAskOnce()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'DebateVerse' && !featureFlagsStore.getFeatureDebateverse()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'SchoolZone' && !featureFlagsStore.getFeatureSchoolZone()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'KnowledgeSpace' && !featureFlagsStore.getFeatureKnowledgeSpace()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }
  if (to.name === 'Library' && !featureFlagsStore.getFeatureLibrary()) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }

  // Redirect authenticated users away from guest-only pages
  if (to.meta.guestOnly && authStore.isAuthenticated) 
  {
    path: '/smart-response',
    name: 'SmartResponse',
    component: () => import('@/pages/SmartResponsePage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, layout: 'main' },
  },
 {
    return next({ name: 'MindMate' })
  }

  next()
})

export default router
