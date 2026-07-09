<script setup lang="ts">
/**
 * Sidebar feature navigation and inline history accordion panels.
 */
import { computed, defineAsyncComponent, inject, reactive } from 'vue'
import { useRoute } from 'vue-router'

import {
  BookOpen,
  Bot,
  Building2,
  ChevronDown,
  FileText,
  Files,
  MessageCircle,
  MessageSquare,
  MessagesSquare,
  Play,
  Settings,
  Share2,
  TrendingUp,
  UserPlus,
  Wand2,
  Watch,
  Waypoints,
  Wrench,
} from '@lucide/vue'

import { appSidebarInjectionKey } from '@/composables/sidebar/useAppSidebar'

const AskOnceHistory = defineAsyncComponent(() => import('./AskOnceHistory.vue'))
const ChatHistory = defineAsyncComponent(() => import('./ChatHistory.vue'))
const ChunkTestHistory = defineAsyncComponent(() => import('./ChunkTestHistory.vue'))
const DebateHistory = defineAsyncComponent(() => import('./DebateHistory.vue'))
const DiagramHistory = defineAsyncComponent(() => import('./DiagramHistory.vue'))
const KnowledgeSpaceHistory = defineAsyncComponent(() => import('./KnowledgeSpaceHistory.vue'))
const LibraryCommentsHistory = defineAsyncComponent(() => import('./LibraryCommentsHistory.vue'))
const WorkshopChatHistory = defineAsyncComponent(() => import('./WorkshopChatHistory.vue'))

const NAV_ICON_SIZE = 18

const _raw = inject(appSidebarInjectionKey)
if (!_raw) {
  throw new Error('AppSidebarNav must be used inside AppSidebar')
}
const s = reactive(_raw)

const route = useRoute()
/** Fullpage `/mindmate`: show more chats in the sidebar by default (API returns up to 50). */
const mindmatePageChatHistoryLimit = computed(() => (route.path.startsWith('/mindmate') ? 50 : 10))
</script>

<template>
  <div
    class="sidebar-nav-scroll"
    :class="{
      'sidebar-nav-scroll--collapsed': s.isCollapsed,
      'sidebar-nav-scroll--workshop': s.workshopExpanded && !s.isCollapsed,
    }"
  >
    <div class="sidebar-nav-main">
      <!-- MindMate: chat history with collab sessions pinned at top of the list -->
      <div
        class="sidebar-nav-mind-section"
        :class="{
          'sidebar-nav-mind-section--expanded': s.showPanel('mindmate') || s.showPanel('mindgraph'),
        }"
      >
        <el-tooltip
          :content="s.mindMateNavLabel"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('mindmate')"
            @click="s.setMode('mindmate')"
          >
            <MessageSquare
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.mindMateNavLabel }}</span
            >
          </div>
        </el-tooltip>
        <transition name="panel-slide">
          <div
            v-if="s.showPanel('mindmate')"
            class="sidebar-panel sidebar-panel--fill"
          >
            <ChatHistory
              compact
              :initial-visible-limit="mindmatePageChatHistoryLimit"
              :show-collab-sessions="s.showMindmateCollabSessions"
            />
          </div>
        </transition>

        <el-tooltip
          :content="s.t('sidebar.mindGraph')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('mindgraph')"
            @click="s.setMode('mindgraph')"
          >
            <Waypoints
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.mindGraph') }}</span
            >
          </div>
        </el-tooltip>
        <transition name="panel-slide">
          <div
            v-if="s.showPanel('mindgraph')"
            class="sidebar-panel sidebar-panel--fill"
          >
            <DiagramHistory @select="s.handleDiagramSelect" />
          </div>
        </transition>
      </div>

      <div
        class="sidebar-nav-rest"
        :class="{
          'sidebar-nav-rest--below-history': s.showPanel('mindmate') || s.showPanel('mindgraph'),
        }"
      >
        <!-- Knowledge Space -->
        <el-tooltip
          v-if="s.isAuthenticated && s.featureKnowledgeSpace && !s.hideKnowledgeSpaceNav"
          :content="s.t('sidebar.knowledgeSpace')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('knowledge-space')"
            @click="s.setMode('knowledge-space')"
          >
            <FileText
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.knowledgeSpace') }}</span
            >
          </div>
        </el-tooltip>
        <transition name="panel-slide">
          <div
            v-if="
              s.isAuthenticated &&
              s.featureKnowledgeSpace &&
              !s.hideKnowledgeSpaceNav &&
              s.showPanel('knowledge-space')
            "
            class="sidebar-panel"
          >
            <KnowledgeSpaceHistory />
          </div>
        </transition>

        <!-- Chunk Test -->
        <el-tooltip
          v-if="s.isAuthenticated && s.featureRagChunkTest && !s.hideKnowledgeSpaceNav"
          :content="s.t('sidebar.chunkTest')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('chunk-test')"
            @click="s.setMode('chunk-test')"
          >
            <Wrench
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.chunkTest') }}</span
            >
          </div>
        </el-tooltip>
        <transition name="panel-slide">
          <div
            v-if="
              s.isAuthenticated &&
              s.featureRagChunkTest &&
              !s.hideKnowledgeSpaceNav &&
              s.showPanel('chunk-test')
            "
            class="sidebar-panel"
          >
            <ChunkTestHistory />
          </div>
        </transition>

        <!-- AskOnce -->
        <el-tooltip
          v-if="s.featureAskOnce"
          :content="s.t('askonce.title')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('askonce')"
            @click="s.setMode('askonce')"
          >
            <Wand2
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('askonce.title') }}</span
            >
          </div>
        </el-tooltip>
        <transition name="panel-slide">
          <div
            v-if="s.featureAskOnce && s.showPanel('askonce')"
            class="sidebar-panel"
          >
            <AskOnceHistory />
          </div>
        </transition>

        <!-- Debateverse -->
        <el-tooltip
          v-if="s.featureDebateverse"
          :content="s.t('sidebar.debateverse')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('debateverse')"
            @click="s.setMode('debateverse')"
          >
            <MessageCircle
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.debateverse') }}</span
            >
          </div>
        </el-tooltip>
        <transition name="panel-slide">
          <div
            v-if="s.featureDebateverse && s.showPanel('debateverse')"
            class="sidebar-panel"
          >
            <DebateHistory />
          </div>
        </transition>

        <!-- School Zone -->
        <el-tooltip
          v-if="s.hasOrganization && s.featureSchoolZone"
          :content="s.t('sidebar.schoolZone')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('school-zone')"
            @click="s.setMode('school-zone')"
          >
            <Building2
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.schoolZone') }}</span
            >
          </div>
        </el-tooltip>

        <!-- Templates -->
        <el-tooltip
          v-if="s.featureTemplate"
          :content="s.t('sidebar.templateResources')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('template')"
            @click="s.setMode('template')"
          >
            <Files
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.templateResources') }}</span
            >
          </div>
        </el-tooltip>

        <!-- Courses -->
        <el-tooltip
          v-if="s.featureCourse"
          :content="s.t('sidebar.courses')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('course')"
            @click="s.setMode('course')"
          >
            <Play
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.courses') }}</span
            >
          </div>
        </el-tooltip>

        <!-- Community -->
        <el-tooltip
          v-if="s.featureCommunity"
          :content="s.t('sidebar.community')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('community')"
            @click="s.setMode('community')"
          >
            <Share2
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.community') }}</span
            >
          </div>
        </el-tooltip>

        <!-- Library -->
        <el-tooltip
          v-if="s.featureLibrary"
          :content="s.t('sidebar.library')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('library')"
            @click="s.setMode('library')"
          >
            <BookOpen
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
              >{{ s.t('sidebar.library') }}</span
            >
          </div>
        </el-tooltip>
        <transition name="panel-slide">
          <div
            v-if="s.featureLibrary && s.showPanel('library')"
            class="sidebar-panel"
          >
            <LibraryCommentsHistory />
          </div>
        </transition>

        <!-- Single management tab (e.g. invite users for experts) -->
        <el-tooltip
          v-if="s.isManagementPanelUser && s.singleAdminNavTab"
          :content="s.singleAdminNavTab.label"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('admin')"
            @click="s.openDirectAdminTab()"
          >
            <UserPlus
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label"
            >
              {{ s.singleAdminNavTab.label }}
            </span>
          </div>
        </el-tooltip>

        <!-- Management panel (expandable sub-nav) -->
        <el-tooltip
          v-if="s.isManagementPanelUser && s.showManagementPanelSubnav"
          :content="s.t('admin.title')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('admin')"
            @click="s.setMode('admin')"
          >
            <Settings
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label admin-menu-title"
            >
              {{ s.t('admin.title') }}
              <ChevronDown
                class="admin-expand-chevron"
                :class="{ 'admin-expand-chevron--open': s.managementPanelExpanded }"
              />
            </span>
          </div>
        </el-tooltip>
        <transition name="admin-slide">
          <div
            v-if="s.managementPanelExpanded && !s.isCollapsed && s.showManagementPanelSubnav"
            class="admin-subnav"
          >
            <template
              v-for="tab in s.adminNavTabs"
              :key="tab.name"
            >
              <template v-if="tab.name === 'data_center'">
                <button
                  type="button"
                  class="nav-subitem nav-subitem--parent"
                  :class="s.adminSubItemClass('data_center')"
                  @click="s.toggleDataCenterNav()"
                >
                  <span>{{ tab.label }}</span>
                  <ChevronDown
                    class="admin-expand-chevron admin-expand-chevron--nested"
                    :class="{ 'admin-expand-chevron--open': s.dataCenterNavExpanded }"
                  />
                </button>
                <div
                  v-if="s.dataCenterNavExpanded"
                  class="admin-subnav-nested"
                >
                  <button
                    v-for="view in s.dataCenterNavViews"
                    :key="view.name"
                    type="button"
                    class="nav-subitem nav-subitem--nested"
                    :class="s.dataCenterSubItemClass(view.name)"
                    @click="s.navigateDataCenterView(view.name)"
                  >
                    {{ view.label }}
                  </button>
                </div>
              </template>
              <template v-else-if="tab.name === 'feature_dev'">
                <button
                  type="button"
                  class="nav-subitem nav-subitem--parent"
                  :class="s.adminSubItemClass('feature_dev')"
                  @click="s.toggleFeatureDevNav()"
                >
                  <span>{{ tab.label }}</span>
                  <ChevronDown
                    class="admin-expand-chevron admin-expand-chevron--nested"
                    :class="{ 'admin-expand-chevron--open': s.featureDevNavExpanded }"
                  />
                </button>
                <div
                  v-if="s.featureDevNavExpanded"
                  class="admin-subnav-nested"
                >
                  <button
                    v-for="item in s.featureDevNavItems"
                    :key="item.name"
                    type="button"
                    class="nav-subitem nav-subitem--nested"
                    :class="s.featureDevSubItemClass(item.name)"
                    @click="s.navigateFeatureDevSubtab(item.name)"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </template>
              <template v-else-if="tab.name === 'settings'">
                <button
                  type="button"
                  class="nav-subitem nav-subitem--parent"
                  :class="s.adminSubItemClass('settings')"
                  @click="s.toggleSettingsNav()"
                >
                  <span>{{ tab.label }}</span>
                  <ChevronDown
                    class="admin-expand-chevron admin-expand-chevron--nested"
                    :class="{ 'admin-expand-chevron--open': s.settingsNavExpanded }"
                  />
                </button>
                <div
                  v-if="s.settingsNavExpanded"
                  class="admin-subnav-nested"
                >
                  <button
                    v-for="item in s.settingsNavItems"
                    :key="item.name"
                    type="button"
                    class="nav-subitem nav-subitem--nested"
                    :class="s.settingsSubItemClass(item.name)"
                    @click="s.navigateSettingsSubtab(item.name)"
                  >
                    {{ item.label }}
                  </button>
                </div>
              </template>
              <button
                v-else
                type="button"
                class="nav-subitem"
                :class="s.adminSubItemClass(tab.name)"
                @click="s.navigateAdminTab(tab.name)"
              >
                {{ tab.label }}
              </button>
            </template>
          </div>
        </transition>

        <!-- Workshop Chat (admin & school managers) -->
        <el-tooltip
          v-if="s.canAccessWorkshopChat"
          :content="s.t('workshop.title')"
          placement="right"
          :disabled="!s.isCollapsed"
        >
          <div
            class="nav-item"
            :class="s.navItemClass('workshop-chat')"
            @click="s.setMode('workshop-chat')"
          >
            <MessagesSquare
              class="nav-icon"
              :size="NAV_ICON_SIZE"
            />
            <span
              v-if="!s.isCollapsed"
              class="nav-label ws-menu-title"
            >
              {{ s.t('workshop.title') }}
              <ChevronDown
                class="ws-expand-chevron"
                :class="{ 'ws-expand-chevron--open': s.workshopExpanded }"
              />
            </span>
          </div>
        </el-tooltip>
        <transition name="ws-slide">
          <div
            v-if="s.workshopExpanded && !s.isCollapsed && s.canAccessWorkshopChat"
            class="workshop-panel-host"
          >
            <WorkshopChatHistory />
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Navigation: main list scrolls; admin block stays at bottom above account footer */
.sidebar-nav-scroll {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  padding: 8px 12px;
}

.sidebar-nav-main {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar-nav-scroll--workshop .sidebar-nav-main {
  overflow: hidden;
}

.sidebar-nav-mind-section {
  display: flex;
  flex-direction: column;
  flex: 0 0 auto;
  min-height: 0;
  overflow: hidden;
}

.sidebar-nav-mind-section--expanded {
  flex: 1 1 0;
  min-height: 0;
}

.sidebar-nav-rest {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

.sidebar-nav-rest--below-history {
  flex: 0 1 auto;
  flex-shrink: 12;
}

.sidebar-nav-scroll--collapsed {
  padding: 8px;
}

.sidebar-nav-scroll--collapsed .sidebar-nav-main {
  overflow-y: auto;
}

/* Custom nav items (replaces el-menu for inline accordion support) */
.nav-item {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 16px;
  border-radius: 8px;
  margin-bottom: 4px;
  font-weight: 500;
  font-size: 14px;
  color: #57534e;
  cursor: pointer;
  transition:
    background-color 0.15s,
    color 0.15s;
  user-select: none;
  flex-shrink: 0;
}

.nav-item:hover {
  background-color: #f5f5f4;
  color: #1c1917;
}
.nav-item.is-active {
  background-color: #1c1917;
  color: white;
}
.nav-item.is-active .nav-icon {
  color: white;
}
.nav-item .nav-icon {
  margin-right: 8px;
  flex-shrink: 0;
}
.nav-item--collapsed {
  justify-content: center;
  padding: 0;
}
.nav-item--collapsed .nav-icon {
  margin-right: 0;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.nav-divider {
  height: 1px;
  background-color: #e7e5e4;
  margin: 4px 0;
  flex-shrink: 0;
}

/* Inline history panels (accordion) */
.sidebar-panel {
  max-height: 40vh;
  overflow-y: auto;
  overflow-x: hidden;
  flex-shrink: 0;
}

.sidebar-panel.sidebar-panel--fill {
  flex: 1 1 0;
  min-height: 0;
  max-height: none;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.sidebar-panel::-webkit-scrollbar {
  width: 4px;
}
.sidebar-panel::-webkit-scrollbar-track {
  background: transparent;
}
.sidebar-panel::-webkit-scrollbar-thumb {
  background-color: #d6d3d1;
  border-radius: 2px;
}
.sidebar-panel::-webkit-scrollbar-thumb:hover {
  background-color: #a8a29e;
}

.workshop-panel-host {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Panel slide transition (for accordion history panels) */
.panel-slide-enter-active {
  transition:
    max-height 0.3s ease,
    opacity 0.3s ease;
  overflow: hidden;
}
.panel-slide-leave-active {
  transition:
    max-height 0.25s ease,
    opacity 0.25s ease;
  overflow: hidden;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
.panel-slide-enter-to,
.panel-slide-leave-from {
  max-height: 100dvh;
  opacity: 1;
}

.nav-item.is-active .admin-expand-chevron {
  color: rgba(255, 255, 255, 0.7);
}

.admin-menu-title {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
}

.admin-expand-chevron {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: #a8a29e;
  transition: transform 0.2s ease;
  transform: rotate(-90deg);
}

.admin-expand-chevron--open {
  transform: rotate(0deg);
}

.admin-subnav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 4px;
}

.nav-subitem {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 40px;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: 8px;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 500;
  color: #78716c;
  cursor: pointer;
  transition:
    background-color 0.15s,
    color 0.15s;
}

.nav-subitem:hover {
  background-color: #f5f5f4;
  color: #1c1917;
}

.nav-subitem.is-active {
  background-color: #e7e5e4;
  color: #1c1917;
}

.nav-subitem--parent {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.admin-subnav-nested {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 2px;
}

.nav-subitem--nested {
  min-height: 36px;
  padding-left: 28px;
  font-size: 13px;
  color: #78716c;
}

.nav-subitem--deep {
  min-height: 34px;
  padding-left: 40px;
  font-size: 12px;
}

.admin-subnav-nested--deep {
  margin-bottom: 0;
}

.admin-expand-chevron--nested {
  width: 12px;
  height: 12px;
}

.admin-slide-enter-active {
  transition: all 0.25s ease;
  overflow: hidden;
}

.admin-slide-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.admin-slide-enter-from,
.admin-slide-leave-to {
  max-height: 0;
  opacity: 0;
}

.admin-slide-enter-to,
.admin-slide-leave-from {
  max-height: 520px;
  opacity: 1;
}

/* Workshop chevron indicator */
.ws-menu-title {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
}

.ws-expand-chevron {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: #a8a29e;
  transition: transform 0.2s ease;
  transform: rotate(-90deg);
}

.ws-expand-chevron--open {
  transform: rotate(0deg);
}
.nav-item.is-active .ws-expand-chevron {
  color: rgba(255, 255, 255, 0.7);
}

/* Workshop panel slide transition */
.ws-slide-enter-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.ws-slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.ws-slide-enter-from,
.ws-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
.ws-slide-enter-to,
.ws-slide-leave-from {
  max-height: 100vh;
  opacity: 1;
}
</style>
