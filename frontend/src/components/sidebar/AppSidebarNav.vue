<script setup lang="ts">
/**
 * Sidebar feature navigation and inline history accordion panels.
 */
import { computed, inject, reactive } from 'vue'
import { useRoute } from 'vue-router'

import {
  ChatDotRound,
  ChatLineSquare,
  Connection,
  Document,
  Files,
  MagicStick,
  OfficeBuilding,
  Reading,
  Share,
  Tools,
  TrendCharts,
  VideoPlay,
} from '@element-plus/icons-vue'

import { Bot, ChevronDown, MessageSquare, Settings, Watch } from 'lucide-vue-next'

import { appSidebarInjectionKey } from '@/composables/sidebar/useAppSidebar'

import AskOnceHistory from './AskOnceHistory.vue'
import ChatHistory from './ChatHistory.vue'
import ChunkTestHistory from './ChunkTestHistory.vue'
import DebateHistory from './DebateHistory.vue'
import DiagramHistory from './DiagramHistory.vue'
import KnowledgeSpaceHistory from './KnowledgeSpaceHistory.vue'
import LibraryCommentsHistory from './LibraryCommentsHistory.vue'
import WorkshopChatHistory from './WorkshopChatHistory.vue'

const _raw = inject(appSidebarInjectionKey)
if (!_raw) {
  throw new Error('AppSidebarNav must be used inside AppSidebar')
}
const s = reactive(_raw)

const route = useRoute()
/** Fullpage `/mindmate`: show more chats in the sidebar by default (API returns up to 50). */
const mindmatePageChatHistoryLimit = computed(() =>
  route.path.startsWith('/mindmate') ? 50 : 10
)
</script>

<template>
  <!-- Simplified UI on MindMate: conversation history only (no module list) -->
  <template v-if="s.isSimplifiedMindmateOnlyNav">
    <div
      v-if="!s.isCollapsed"
      class="sidebar-nav-scroll sidebar-nav-scroll--mindmate-only"
    >
      <ChatHistory
        compact
        :initial-visible-limit="mindmatePageChatHistoryLimit"
      />
    </div>
    <div
      v-else
      class="sidebar-nav-scroll sidebar-nav-scroll--collapsed flex flex-col items-center pt-2"
    >
      <el-tooltip
        :content="s.t('sidebar.expandSidebar')"
        placement="right"
      >
        <button
          type="button"
          class="nav-item nav-item--collapsed"
          :aria-label="s.t('sidebar.expandSidebar')"
          @click="s.toggleSidebar"
        >
          <el-icon><ChatLineSquare /></el-icon>
        </button>
      </el-tooltip>
    </div>
  </template>
  <div
    v-else
    class="sidebar-nav-scroll"
    :class="{
      'sidebar-nav-scroll--collapsed': s.isCollapsed,
      'sidebar-nav-scroll--workshop': s.workshopExpanded && !s.isCollapsed,
    }"
  >
    <!-- MindMate -->
    <el-tooltip
      :content="s.t('sidebar.mindMate')"
      placement="right"
      :disabled="!s.isCollapsed"
    >
      <div
        class="nav-item"
        :class="s.navItemClass('mindmate')"
        @click="s.setMode('mindmate')"
      >
        <el-icon><ChatLineSquare /></el-icon>
        <span
          v-if="!s.isCollapsed"
          class="nav-label"
          >{{ s.t('sidebar.mindMate') }}</span
        >
      </div>
    </el-tooltip>
    <transition name="panel-slide">
      <div
        v-if="s.showPanel('mindmate')"
        class="sidebar-panel"
      >
        <ChatHistory :initial-visible-limit="mindmatePageChatHistoryLimit" />
      </div>
    </transition>

    <!-- MindGraph -->
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
        <el-icon><Connection /></el-icon>
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
        class="sidebar-panel"
      >
        <DiagramHistory @select="s.handleDiagramSelect" />
      </div>
    </transition>

    <!-- Knowledge Space -->
    <el-tooltip
      v-if="s.isAuthenticated && s.featureKnowledgeSpace"
      :content="s.t('sidebar.knowledgeSpace')"
      placement="right"
      :disabled="!s.isCollapsed"
    >
      <div
        class="nav-item"
        :class="s.navItemClass('knowledge-space')"
        @click="s.setMode('knowledge-space')"
      >
        <el-icon><Document /></el-icon>
        <span
          v-if="!s.isCollapsed"
          class="nav-label"
          >{{ s.t('sidebar.knowledgeSpace') }}</span
        >
      </div>
    </el-tooltip>
    <transition name="panel-slide">
      <div
        v-if="s.isAuthenticated && s.featureKnowledgeSpace && s.showPanel('knowledge-space')"
        class="sidebar-panel"
      >
        <KnowledgeSpaceHistory />
      </div>
    </transition>

    <!-- Chunk Test -->
    <el-tooltip
      v-if="s.isAuthenticated && s.featureRagChunkTest"
      :content="s.t('sidebar.chunkTest')"
      placement="right"
      :disabled="!s.isCollapsed"
    >
      <div
        class="nav-item"
        :class="s.navItemClass('chunk-test')"
        @click="s.setMode('chunk-test')"
      >
        <el-icon><Tools /></el-icon>
        <span
          v-if="!s.isCollapsed"
          class="nav-label"
          >{{ s.t('sidebar.chunkTest') }}</span
        >
      </div>
    </el-tooltip>
    <transition name="panel-slide">
      <div
        v-if="s.isAuthenticated && s.featureRagChunkTest && s.showPanel('chunk-test')"
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
        <el-icon><MagicStick /></el-icon>
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
        <el-icon><ChatDotRound /></el-icon>
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
        <el-icon><OfficeBuilding /></el-icon>
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
        <el-icon><Files /></el-icon>
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
        <el-icon><VideoPlay /></el-icon>
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
        <el-icon><Share /></el-icon>
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
        <el-icon><Reading /></el-icon>
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
        <el-icon><MessageSquare /></el-icon>
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

    <!-- Admin / management items (inline, hidden when workshop expanded) -->
    <template v-if="!s.workshopExpanded && (s.isAdminOrManager || s.isAdmin)">
      <div class="nav-divider" />

      <el-tooltip
        v-if="s.isAdmin && s.featureGewe"
        content="Gewe"
        placement="right"
        :disabled="!s.isCollapsed"
      >
        <div
          class="nav-item"
          :class="s.navItemClass('gewe')"
          @click="s.setMode('gewe')"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span
            v-if="!s.isCollapsed"
            class="nav-label"
            >Gewe</span
          >
        </div>
      </el-tooltip>

      <el-tooltip
        v-if="s.isAdminOrManager && s.featureSmartResponse"
        :content="s.t('sidebar.smartResponse')"
        placement="right"
        :disabled="!s.isCollapsed"
      >
        <div
          class="nav-item"
          :class="s.navItemClass('smart-response')"
          @click="s.setMode('smart-response')"
        >
          <el-icon><Watch /></el-icon>
          <span
            v-if="!s.isCollapsed"
            class="nav-label"
            >{{ s.t('sidebar.smartResponse') }}</span
          >
        </div>
      </el-tooltip>

      <el-tooltip
        v-if="s.isAdmin && s.featureTeacherUsage"
        :content="s.t('sidebar.teacherUsage')"
        placement="right"
        :disabled="!s.isCollapsed"
      >
        <div
          class="nav-item"
          :class="s.navItemClass('teacher-usage')"
          @click="s.setMode('teacher-usage')"
        >
          <el-icon><TrendCharts /></el-icon>
          <span
            v-if="!s.isCollapsed"
            class="nav-label"
            >{{ s.t('sidebar.teacherUsage') }}</span
          >
        </div>
      </el-tooltip>

      <el-tooltip
        v-if="s.isAdmin && s.featureMindbot"
        :content="s.t('sidebar.mindbot')"
        placement="right"
        :disabled="!s.isCollapsed"
      >
        <div
          class="nav-item"
          :class="s.navItemClass('mindbot')"
          @click="s.setMode('mindbot')"
        >
          <el-icon><Bot /></el-icon>
          <span
            v-if="!s.isCollapsed"
            class="nav-label"
            >{{ s.t('sidebar.mindbot') }}</span
          >
        </div>
      </el-tooltip>

      <el-tooltip
        v-if="s.isAdminOrManager"
        :content="s.t('admin.schoolDashboard')"
        placement="right"
        :disabled="!s.isCollapsed"
      >
        <div
          class="nav-item"
          :class="s.navItemClass('school-dashboard')"
          @click="s.setMode('school-dashboard')"
        >
          <el-icon><OfficeBuilding /></el-icon>
          <span
            v-if="!s.isCollapsed"
            class="nav-label"
            >{{ s.t('admin.schoolDashboard') }}</span
          >
        </div>
      </el-tooltip>

      <el-tooltip
        v-if="s.isAdmin"
        :content="s.t('admin.title')"
        placement="right"
        :disabled="!s.isCollapsed"
      >
        <div
          class="nav-item"
          :class="s.navItemClass('admin')"
          @click="s.setMode('admin')"
        >
          <el-icon><Settings /></el-icon>
          <span
            v-if="!s.isCollapsed"
            class="nav-label"
            >{{ s.t('admin.title') }}</span
          >
        </div>
      </el-tooltip>
    </template>
  </div>
</template>

<style scoped>
.sidebar-nav-scroll--mindmate-only {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 8px 6px 8px 8px;
}

.sidebar-nav-scroll--mindmate-only :deep(.chat-history) {
  flex: 1;
  min-height: 0;
  border-top: none;
}

button.nav-item {
  appearance: none;
  border: none;
  background: transparent;
  width: 100%;
  font: inherit;
  text-align: center;
}

/* Navigation container (no scroll — only panels scroll internally) */
.sidebar-nav-scroll {
  flex: 1;
  overflow: hidden;
  min-height: 0;
  padding: 8px 12px;
}

.sidebar-nav-scroll--workshop {
  display: flex;
  flex-direction: column;
}

.sidebar-nav-scroll--collapsed {
  padding: 8px;
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
.nav-item.is-active .el-icon {
  color: white;
}
.nav-item .el-icon {
  margin-right: 8px;
  font-size: 18px;
  flex-shrink: 0;
}
.nav-item--collapsed {
  justify-content: center;
  padding: 0;
}
.nav-item--collapsed .el-icon {
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
  max-height: 40vh;
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
