/**
 * AppSidebar navigation state, feature gates, and handlers.
 */
import type { InjectionKey } from 'vue'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore, useMindMateStore, useUIStore } from '@/stores'
import { useAskOnceStore } from '@/stores/askonce'
import type { SavedDiagram } from '@/stores/savedDiagrams'
import { userCanAccessMindbotAdmin } from '@/utils/mindbotAccess'
import { userCanAccessWorkshopChat } from '@/utils/workshopAccess'

export function useAppSidebar() {
  const { t } = useLanguage()
  const router = useRouter()
  const uiStore = useUIStore()
  const authStore = useAuthStore()
  const mindMateStore = useMindMateStore()
  const askOnceStore = useAskOnceStore()
  const {
    featureRagChunkTest,
    featureCourse,
    featureTemplate,
    featureCommunity,
    featureAskOnce,
    featureSchoolZone,
    featureDebateverse,
    featureKnowledgeSpace,
    featureLibrary,
    featureGewe,
    featureSmartResponse,
    featureTeacherUsage,
    featureWorkshopChat,
    featureMindbot,
    workshopChatPreviewOrgIds,
    featureOrgAccess,
  } = useFeatureFlags()

  const isCollapsed = computed(() => uiStore.sidebarCollapsed)

  const currentMode = computed(() => {
    const path = router.currentRoute.value.path
    if (path.startsWith('/mindmate')) return 'mindmate'
    if (path.startsWith('/mindgraph') || path.startsWith('/canvas')) return 'mindgraph'
    if (path.startsWith('/knowledge-space')) return 'knowledge-space'
    if (path.startsWith('/chunk-test')) return 'chunk-test'
    if (path.startsWith('/askonce')) return 'askonce'
    if (path.startsWith('/debateverse')) return 'debateverse'
    if (path.startsWith('/school-zone')) return 'school-zone'
    if (path.startsWith('/template')) return 'template'
    if (path.startsWith('/course')) return 'course'
    if (path.startsWith('/community')) return 'community'
    if (path.startsWith('/library')) return 'library'
    if (path.startsWith('/gewe')) return 'gewe'
    if (path.startsWith('/school-dashboard')) return 'school-dashboard'
    if (path.startsWith('/admin/mindbot')) return 'mindbot'
    if (path.startsWith('/admin')) return 'admin'
    if (path.startsWith('/smart-response')) return 'smart-response'
    if (path.startsWith('/teacher-usage')) return 'teacher-usage'
    if (path.startsWith('/workshop-chat')) return 'workshop-chat'
    return 'mindmate'
  })

  const isAuthenticated = computed(() => authStore.isAuthenticated)

  const hasOrganization = computed(() => {
    return isAuthenticated.value && authStore.user?.schoolId
  })
  const isAdminOrManager = computed(() => authStore.isAdminOrManager)
  const isAdmin = computed(() => authStore.isAdmin)

  const canAccessWorkshopChat = computed(() => {
    if (!featureWorkshopChat.value) {
      return false
    }
    const entry = featureOrgAccess.value.feature_workshop_chat
    return userCanAccessWorkshopChat(
      authStore.isAdminOrManager,
      authStore.user?.schoolId,
      authStore.user?.id,
      workshopChatPreviewOrgIds.value,
      entry
    )
  })

  /** Same rules as router `MindbotAdmin`: feature flag + admin or eligible manager. */
  const canAccessMindbot = computed(() => {
    if (!featureMindbot.value) {
      return false
    }
    const entry = featureOrgAccess.value.feature_mindbot
    return userCanAccessMindbotAdmin(
      authStore.isAdmin,
      authStore.isManager,
      authStore.user?.schoolId,
      authStore.user?.id,
      entry
    )
  })

  const userName = computed(() => authStore.user?.username || '')
  const userSubtitle = computed(() => {
    const schoolName = authStore.user?.schoolName
    return schoolName && schoolName.trim() ? schoolName : t('sidebar.userSubtitleDefault')
  })
  const userAvatar = computed(() => {
    const avatar = authStore.user?.avatar || '🐈‍⬛'
    if (avatar.startsWith('avatar_')) {
      return '🐈‍⬛'
    }
    return avatar
  })

  const showLoginModal = ref(false)
  const showAccountModal = ref(false)
  const showUpdateLogModal = ref(false)
  const showLanguageSettingsModal = ref(false)

  function toggleSidebar() {
    uiStore.toggleSidebar()
  }

  const routeMap: Record<string, string> = {
    mindmate: '/mindmate',
    mindgraph: '/mindgraph',
    'knowledge-space': '/knowledge-space',
    'chunk-test': '/chunk-test',
    askonce: '/askonce',
    debateverse: '/debateverse',
    'school-zone': '/school-zone',
    template: '/template',
    course: '/course',
    community: '/community',
    library: '/library',
    gewe: '/gewe',
    'school-dashboard': '/school-dashboard',
    admin: '/admin',
    'smart-response': '/smart-response',
    'teacher-usage': '/teacher-usage',
    'workshop-chat': '/workshop-chat',
    mindbot: '/admin/mindbot',
  }

  function setMode(index: string) {
    if (currentMode.value === index) {
      expandedPanel.value = expandedPanel.value === index ? null : index
      return
    }

    expandedPanel.value = index
    const r = routeMap[index]
    if (r) {
      router.push(r)
    }
  }

  function openLoginModal() {
    showLoginModal.value = true
  }

  function openAccountModal() {
    showAccountModal.value = true
  }

  function openUpdateLogModal() {
    showUpdateLogModal.value = true
  }

  function openLanguageSettingsModal() {
    showLanguageSettingsModal.value = true
  }

  async function handleLogout() {
    await authStore.logout()
  }

  function startNewChat() {
    mindMateStore.startNewConversation()
    if (currentMode.value !== 'mindmate') {
      router.push('/mindmate')
    }
  }

  function startNewAskOnce() {
    if (!isAuthenticated.value) {
      openLoginModal()
      return
    }
    askOnceStore.startNewConversation()
    if (currentMode.value !== 'askonce') {
      router.push('/askonce')
    }
  }

  function handleLogoClick() {
    if (uiStore.uiVersion === 'international') {
      router.push('/mindgraph')
      return
    }
    if (currentMode.value === 'askonce') {
      startNewAskOnce()
    } else {
      startNewChat()
    }
  }

  async function handleDiagramSelect(diagram: SavedDiagram) {
    router.push({
      path: '/canvas',
      query: { diagramId: diagram.id.toString() },
    })
  }

  const expandedPanel = ref<string | null>(null)
  const workshopExpanded = computed(() => expandedPanel.value === 'workshop-chat')

  function navItemClass(mode: string) {
    return {
      'nav-item--collapsed': isCollapsed.value,
      'is-active': currentMode.value === mode,
    }
  }

  function showPanel(mode: string): boolean {
    return !isCollapsed.value && expandedPanel.value === mode
  }

  /**
   * Keep MindMate vs MindGraph history accordions in sync with the route: only one open,
   * and the active app shows its history (ChatHistory vs DiagramHistory).
   */
  watch(
    currentMode,
    (mode) => {
      if (mode === 'mindmate' || mode === 'mindgraph') {
        expandedPanel.value = mode
        return
      }
      if (expandedPanel.value === 'mindmate' || expandedPanel.value === 'mindgraph') {
        expandedPanel.value = null
      }
    },
    { immediate: true }
  )

  return {
    t,
    router,
    uiStore,
    authStore,
    featureRagChunkTest,
    featureCourse,
    featureTemplate,
    featureCommunity,
    featureAskOnce,
    featureSchoolZone,
    featureDebateverse,
    featureKnowledgeSpace,
    featureLibrary,
    featureGewe,
    featureSmartResponse,
    featureTeacherUsage,
    featureWorkshopChat,
    featureMindbot,
    isCollapsed,
    currentMode,
    hasOrganization,
    isAuthenticated,
    isAdminOrManager,
    isAdmin,
    canAccessWorkshopChat,
    canAccessMindbot,
    userName,
    userSubtitle,
    userAvatar,
    showLoginModal,
    showAccountModal,
    showUpdateLogModal,
    showLanguageSettingsModal,
    toggleSidebar,
    setMode,
    openLoginModal,
    openAccountModal,
    openUpdateLogModal,
    openLanguageSettingsModal,
    handleLogout,
    startNewChat,
    startNewAskOnce,
    handleLogoClick,
    handleDiagramSelect,
    expandedPanel,
    workshopExpanded,
    navItemClass,
    showPanel,
  }
}

export type AppSidebarContext = ReturnType<typeof useAppSidebar>

export const appSidebarInjectionKey: InjectionKey<AppSidebarContext> = Symbol('appSidebar')
