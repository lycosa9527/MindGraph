/**
 * AppSidebar navigation state, feature gates, and handlers.
 */
import type { InjectionKey } from 'vue'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { formatThinkingCoinBalance } from '@/composables/auth/useThinkingCoins'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useLanguage } from '@/composables/core/useLanguage'
import { useAdminPanelTabs } from '@/composables/admin/useAdminPanelTabs'
import {
  canViewDataCenterSubView,
  DATA_CENTER_VIEWS,
  defaultDataCenterView,
  isDataCenterView,
  visibleDataCenterViews,
  type DataCenterView,
} from '@/composables/admin/adminDataCenterViews'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminFeatureDevNav } from '@/composables/admin/useAdminFeatureDevNav'
import { defaultFeatureDevSubtab } from '@/composables/admin/adminFeatureDevNav'
import { useAdminSettingsNav } from '@/composables/admin/useAdminSettingsNav'
import { useMindMateBranding } from '@/composables/mindmate/useMindMateBranding'
import { useAuthStore, useMindMateStore, useUIStore } from '@/stores'
import { useAskOnceStore } from '@/stores/askonce'
import type { SavedDiagram } from '@/stores/savedDiagrams'
import type { ThinkingCoinEarnTask, ThinkingCoinsWallet } from '@/types/thinkingCoins'
import { apiRequestJson } from '@/utils/apiClient'
import { userCanAccessMindbotAdmin } from '@/utils/mindbotAccess'
import { getRolePillStyle } from '@/utils/userRoleDisplay'
import { userCanAccessWorkshopChat } from '@/utils/workshopAccess'
import { resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'

/** Max graphemes for org name in sidebar header (total label ≈ 10 incl. 专属版). */
const ORG_EDITION_MAX_ORG_NAME_LENGTH = 7

function truncateGraphemes(text: string, maxLength: number): string {
  const graphemes = [...text]
  if (graphemes.length <= maxLength) {
    return text
  }
  return graphemes.slice(0, maxLength).join('')
}

export function useAppSidebar() {
  const { t } = useLanguage()
  const router = useRouter()
  const uiStore = useUIStore()
  const authStore = useAuthStore()
  const mindMateStore = useMindMateStore()
  const askOnceStore = useAskOnceStore()
  const { displayName: mindMateNavLabel } = useMindMateBranding()
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
    featureKittyAgent,
    featureMindmateExport,
    featureWorkshopChat,
    featureMindbot,
    workshopChatPreviewOrgIds,
    featureOrgAccess,
    featureThinkingCoins,
  } = useFeatureFlags()

  const isCollapsed = computed(() => uiStore.sidebarCollapsed)

  const currentMode = computed(() => {
    const path = router.currentRoute.value.path
    if (path.startsWith('/mindmate')) return 'mindmate'
    if (
      path.startsWith('/mindgraph') ||
      path.startsWith('/canvas') ||
      path.startsWith('/m/mindgraph') ||
      path.startsWith('/m/canvas')
    ) {
      return 'mindgraph'
    }
    if (path.startsWith('/knowledge-space')) return 'knowledge-space'
    if (path.startsWith('/chunk-test')) return 'chunk-test'
    if (path.startsWith('/askonce')) return 'askonce'
    if (path.startsWith('/debateverse')) return 'debateverse'
    if (path.startsWith('/school-zone')) return 'school-zone'
    if (path.startsWith('/template')) return 'template'
    if (path.startsWith('/course')) return 'course'
    if (path.startsWith('/community')) return 'community'
    if (path.startsWith('/library')) return 'library'
    if (
      path.startsWith('/gewe') ||
      path.startsWith('/school-dashboard') ||
      path.startsWith('/smart-response') ||
      path.startsWith('/teacher-usage') ||
      path.startsWith('/admin')
    ) {
      return 'admin'
    }
    if (path.startsWith('/workshop-chat')) return 'workshop-chat'
    return 'mindmate'
  })

  const isAuthenticated = computed(() => authStore.isAuthenticated)

  const hasOrganization = computed(() => {
    return isAuthenticated.value && authStore.user?.schoolId
  })
  const isAdminOrManager = computed(() => authStore.isAdminOrManager)
  const isAdmin = computed(() => authStore.isAdmin)
  const isManagementPanelUser = computed(() => authStore.isManagementPanelUser)
  const { tabs: adminNavTabs, loadCapabilities: loadAdminNavCapabilities } = useAdminPanelTabs({
    loadOnMount: false,
  })
  const singleAdminNavTab = computed(() => {
    const visible = adminNavTabs.value
    return visible.length === 1 ? visible[0] : null
  })
  const showManagementPanelSubnav = computed(() => adminNavTabs.value.length > 1)
  const { can, canViewSettingsSubtab, capabilities } = useAdminAccess()
  const expandedPanel = ref<string | null>(null)
  const dataCenterNavExpanded = ref(false)

  const currentAdminTab = computed((): string | null => {
    const path = router.currentRoute.value.path
    if (!path.startsWith('/admin')) {
      return null
    }
    const tab = router.currentRoute.value.query.tab
    return typeof tab === 'string' && tab.trim() ? tab : 'data_center'
  })

  const managementPanelExpanded = computed(() => expandedPanel.value === 'admin')

  const dataCenterNavViews = computed(() => {
    const allowed = new Set(visibleDataCenterViews(capabilities.value))
    return DATA_CENTER_VIEWS.filter((view) => allowed.has(view.name)).map((view) => ({
      ...view,
      label: t(view.labelKey),
    }))
  })

  const currentDataCenterView = computed((): DataCenterView | null => {
    if (currentAdminTab.value !== 'data_center') {
      return null
    }
    const raw = router.currentRoute.value.query.view
    if (typeof raw === 'string' && isDataCenterView(raw)) {
      return raw
    }
    return defaultDataCenterView(can('scope.global') && can('tab.data_center.view'))
  })

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

  /** Same rules as server `require_mindbot_admin_access` — superadmin only. */
  const canAccessMindbot = computed(() => {
    if (!featureMindbot.value) {
      return false
    }
    return userCanAccessMindbotAdmin(
      authStore.isAdmin,
      authStore.isManager,
      authStore.user?.schoolId,
      authStore.user?.id,
      featureOrgAccess.value.feature_mindbot
    )
  })

  const thinkingCoinsEligible = computed(
    () => featureThinkingCoins.value && authStore.user?.thinkingCoins?.eligible === true
  )
  const thinkingCoinsBalance = computed(() => authStore.user?.thinkingCoins?.balance ?? 0)

  const thinkingCoinsBalanceFormatted = computed(() =>
    formatThinkingCoinBalance(thinkingCoinsBalance.value)
  )

  const userName = computed(() => authStore.user?.username || '')
  const userRolePill = computed(() => {
    if (!authStore.user?.role) {
      return null
    }
    const style = getRolePillStyle(authStore.user.role, authStore.user.schoolTier)
    if (!style) {
      return null
    }
    return {
      label: t(style.labelKey),
      bgClass: style.bgClass,
      textClass: style.textClass,
      borderClass: style.borderClass,
    }
  })
  const orgEditionLabel = computed(() => {
    const schoolName = authStore.user?.schoolName?.trim()
    if (schoolName) {
      const org = truncateGraphemes(schoolName, ORG_EDITION_MAX_ORG_NAME_LENGTH)
      return t('sidebar.orgEdition', { org })
    }
    return t('sidebar.userSubtitleDefault')
  })
  const orgEditionTooltip = computed(() => {
    const schoolName = authStore.user?.schoolName?.trim()
    if (!schoolName) {
      return ''
    }
    return t('sidebar.orgEdition', { org: schoolName })
  })
  const userAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))

  const showLoginModal = ref(false)
  const showAccountModal = ref(false)
  const showThinkingCoinsModal = ref(false)
  const thinkingCoinsModalTab = ref<'wallet' | 'subscription'>('wallet')
  const showUpdateLogModal = ref(false)
  const showLanguageSettingsModal = ref(false)
  const thinkingCoinEarnTasks = ref<ThinkingCoinEarnTask[]>([])
  let thinkingCoinWalletFetchGeneration = 0

  async function refreshThinkingCoinEarnTasks(): Promise<void> {
    if (!thinkingCoinsEligible.value) {
      thinkingCoinEarnTasks.value = []
      return
    }
    const generation = ++thinkingCoinWalletFetchGeneration
    try {
      const data = await apiRequestJson<ThinkingCoinsWallet>('/api/auth/thinking-coins/wallet', {
        method: 'GET',
      })
      if (generation !== thinkingCoinWalletFetchGeneration) {
        return
      }
      thinkingCoinEarnTasks.value = data.earn_tasks ?? []
      if (data.eligible) {
        authStore.patchThinkingCoinsSummary({
          balance: data.balance,
          eligible: data.eligible,
        })
      }
    } catch {
      if (generation === thinkingCoinWalletFetchGeneration) {
        thinkingCoinEarnTasks.value = []
      }
    }
  }

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
    admin: '/admin',
    'workshop-chat': '/workshop-chat',
  }

  const settingsNav = useAdminSettingsNav({
    t,
    canViewSettingsSubtab,
    featureGewe,
    featureLibrary,
    currentAdminTab,
  })

  const featureDevNav = useAdminFeatureDevNav({
    t,
    canViewSettingsSubtab,
    featureSmartResponse,
    featureTeacherUsage,
    featureKittyAgent,
    featureMindmateExport,
    currentAdminTab,
  })

  function openDirectAdminTab(): void {
    const tab = singleAdminNavTab.value
    if (!tab) {
      return
    }
    navigateAdminTab(tab.name)
  }

  function navigateAdminTab(tabName: string, view?: string): void {
    if (showManagementPanelSubnav.value) {
      expandedPanel.value = 'admin'
    }
    const query: Record<string, string> = { tab: tabName }
    if (tabName === 'feature_dev') {
      const first = defaultFeatureDevSubtab(featureDevNav.visibilityOptions.value)
      if (first) {
        query.subtab = featureDevNav.currentFeatureDevSubtab.value ?? first
      }
    }
    if (tabName === 'settings') {
      query.subtab = settingsNav.currentSettingsSubtab.value ?? 'roles'
    }
    if (tabName === 'data_center') {
      let resolvedView =
        view && isDataCenterView(view)
          ? view
          : defaultDataCenterView(can('scope.global') && can('tab.data_center.view'))
      if (!canViewDataCenterSubView(resolvedView, capabilities.value)) {
        resolvedView = defaultDataCenterView(can('scope.global') && can('tab.data_center.view'))
      }
      query.view = resolvedView
    }
    const orgId = router.currentRoute.value.query.organization_id
    if (typeof orgId === 'string' && orgId.trim()) {
      query.organization_id = orgId
    }
    void router.push({ path: '/admin', query })
  }

  function navigateDataCenterView(view: DataCenterView): void {
    navigateAdminTab('data_center', view)
  }

  function toggleDataCenterNav(): void {
    if (currentAdminTab.value === 'data_center') {
      dataCenterNavExpanded.value = !dataCenterNavExpanded.value
      return
    }
    dataCenterNavExpanded.value = true
    navigateAdminTab('data_center')
  }

  function toggleManagementPanel(): void {
    if (isCollapsed.value) {
      const tab = currentAdminTab.value ?? adminNavTabs.value[0]?.name ?? 'data_center'
      if (tab === 'data_center') {
        navigateAdminTab(tab, currentDataCenterView.value ?? undefined)
      } else {
        navigateAdminTab(tab)
      }
      return
    }
    if (currentMode.value === 'admin') {
      expandedPanel.value = expandedPanel.value === 'admin' ? null : 'admin'
      return
    }
    expandedPanel.value = 'admin'
    const tab = adminNavTabs.value[0]?.name ?? 'data_center'
    navigateAdminTab(tab)
  }

  function adminSubItemClass(tabName: string) {
    return {
      'is-active': currentAdminTab.value === tabName,
    }
  }

  function dataCenterSubItemClass(view: DataCenterView) {
    return {
      'is-active':
        currentAdminTab.value === 'data_center' && currentDataCenterView.value === view,
    }
  }

  function setMode(index: string) {
    if (index === 'admin') {
      toggleManagementPanel()
      return
    }
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

  function openThinkingCoinsUpgrade() {
    void refreshThinkingCoinEarnTasks()
    void router.push('/thinking-coins/upgrade')
  }

  function openThinkingCoinsModal(tab: 'wallet' | 'subscription' = 'wallet') {
    if (tab === 'subscription') {
      openThinkingCoinsUpgrade()
      return
    }
    thinkingCoinsModalTab.value = tab
    showThinkingCoinsModal.value = true
    void refreshThinkingCoinEarnTasks()
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

  watch(
    () => router.currentRoute.value.path,
    (path) => {
      if (path.startsWith('/admin')) {
        if (showManagementPanelSubnav.value) {
          expandedPanel.value = 'admin'
        }
      } else if (expandedPanel.value === 'admin') {
        expandedPanel.value = null
      }
    },
    { immediate: true }
  )

  watch(
    currentAdminTab,
    (tab) => {
      if (tab !== 'data_center') {
        dataCenterNavExpanded.value = false
      }
      if (tab !== 'settings') {
        settingsNav.settingsNavExpanded.value = false
      }
      if (tab !== 'feature_dev') {
        featureDevNav.featureDevNavExpanded.value = false
      }
    },
    { immediate: true }
  )

  watch(
    isManagementPanelUser,
    (allowed) => {
      if (allowed) {
        void loadAdminNavCapabilities()
      }
    },
    { immediate: true }
  )

  watch(
    () =>
      [
        thinkingCoinsEligible.value,
        authStore.user?.id ?? null,
      ] as const,
    ([eligible]) => {
      if (eligible) {
        void refreshThinkingCoinEarnTasks()
        return
      }
      thinkingCoinWalletFetchGeneration += 1
      thinkingCoinEarnTasks.value = []
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
    isManagementPanelUser,
    adminNavTabs,
    singleAdminNavTab,
    showManagementPanelSubnav,
    openDirectAdminTab,
    currentAdminTab,
    dataCenterNavViews,
    dataCenterNavExpanded,
    currentDataCenterView,
    navigateDataCenterView,
    toggleDataCenterNav,
    dataCenterSubItemClass,
    managementPanelExpanded,
    navigateAdminTab,
    toggleManagementPanel,
    adminSubItemClass,
    featureDevNavExpanded: featureDevNav.featureDevNavExpanded,
    featureDevNavItems: featureDevNav.featureDevNavItems,
    currentFeatureDevSubtab: featureDevNav.currentFeatureDevSubtab,
    navigateFeatureDevSubtab: featureDevNav.navigateFeatureDevSubtab,
    toggleFeatureDevNav: featureDevNav.toggleFeatureDevNav,
    featureDevSubItemClass: featureDevNav.featureDevSubItemClass,
    settingsNavExpanded: settingsNav.settingsNavExpanded,
    currentSettingsSubtab: settingsNav.currentSettingsSubtab,
    settingsNavItems: settingsNav.settingsNavItems,
    navigateSettingsSubtab: settingsNav.navigateSettingsSubtab,
    toggleSettingsNav: settingsNav.toggleSettingsNav,
    settingsSubItemClass: settingsNav.settingsSubItemClass,
    canAccessWorkshopChat,
    canAccessMindbot,
    mindMateNavLabel,
    userName,
    userRolePill,
    orgEditionLabel,
    orgEditionTooltip,
    userAvatar,
    showLoginModal,
    showAccountModal,
    showThinkingCoinsModal,
    thinkingCoinsModalTab,
    thinkingCoinsEligible,
    thinkingCoinsBalance,
    thinkingCoinsBalanceFormatted,
    thinkingCoinEarnTasks,
    refreshThinkingCoinEarnTasks,
    showUpdateLogModal,
    showLanguageSettingsModal,
    toggleSidebar,
    setMode,
    openLoginModal,
    openAccountModal,
    openThinkingCoinsModal,
    openThinkingCoinsUpgrade,
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
