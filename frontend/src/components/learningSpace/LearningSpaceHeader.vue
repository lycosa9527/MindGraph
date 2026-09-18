<script setup lang="ts">
/**
 * Learning Space top tabs (works beside the main app sidebar).
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  BookOpen,
  ClipboardList,
  GraduationCap,
  Home,
  LayoutDashboard,
  PanelLeftOpen,
  Waypoints,
} from '@lucide/vue'

import { useLanguage } from '@/composables'
import type { StudentTab, TeacherTab } from '@/composables/learningSpace/lsHelpers'
import { useUIStore } from '@/stores/ui'

defineProps<{
  mode: 'teacher' | 'student'
  teacherTab: TeacherTab
  studentTab: StudentTab
  pendingBadge: number
  showShellSwitch?: boolean
}>()

const emit = defineEmits<{
  'update:teacherTab': [TeacherTab]
  'update:studentTab': [StudentTab]
  'update:mode': ['teacher' | 'student']
}>()

const { t } = useLanguage()
const route = useRoute()
const uiStore = useUIStore()

const showSidebarExpand = computed(
  () => uiStore.sidebarCollapsed && !route.path.startsWith('/m/')
)

const teacherTabs: { id: TeacherTab; icon: typeof LayoutDashboard; labelKey: string }[] = [
  { id: 'dashboard', icon: LayoutDashboard, labelKey: 'learningSpace.tabDashboard' },
  { id: 'assignments', icon: ClipboardList, labelKey: 'learningSpace.tabAssignments' },
  { id: 'classes', icon: GraduationCap, labelKey: 'learningSpace.tabClasses' },
]

const studentTabs: { id: StudentTab; icon: typeof Home; labelKey: string }[] = [
  { id: 'home', icon: Home, labelKey: 'learningSpace.tabHome' },
  { id: 'assignments', icon: BookOpen, labelKey: 'learningSpace.tabClassAssignments' },
  { id: 'works', icon: Waypoints, labelKey: 'learningSpace.tabMyPortfolio' },
]
</script>

<template>
  <header class="ls-app__header">
    <div class="ls-app__header-inner">
    <button
      v-if="showSidebarExpand"
      type="button"
      class="ls-app__sidebar-toggle"
      :title="t('sidebar.expandSidebar')"
      :aria-label="t('sidebar.expandSidebar')"
      @click="uiStore.toggleSidebar()"
    >
      <PanelLeftOpen :size="18" />
    </button>
    <div class="ls-app__brand">
      <div class="ls-app__brand-title">{{ t('learningSpace.brandTitle') }}</div>
    </div>
    <div
      v-if="showShellSwitch"
      class="ls-app__shell-switch"
    >
      <button
        type="button"
        class="ls-app__tab"
        :class="{ 'ls-app__tab--active': mode === 'teacher' }"
        @click="emit('update:mode', 'teacher')"
      >
        {{ t('learningSpace.modeReview') }}
      </button>
      <button
        type="button"
        class="ls-app__tab"
        :class="{ 'ls-app__tab--active': mode === 'student' }"
        @click="emit('update:mode', 'student')"
      >
        {{ t('learningSpace.modeLearn') }}
      </button>
    </div>

    <nav
      v-if="mode === 'teacher'"
      class="ls-app__tabs"
      role="tablist"
    >
      <button
        v-for="tab in teacherTabs"
        :key="tab.id"
        type="button"
        role="tab"
        class="ls-app__tab"
        :class="{ 'ls-app__tab--active': teacherTab === tab.id }"
        :aria-selected="teacherTab === tab.id"
        @click="emit('update:teacherTab', tab.id)"
      >
        <component
          :is="tab.icon"
          :size="15"
          stroke-width="2"
        />
        <span class="ls-app__tab-text">{{ t(tab.labelKey) }}</span>
        <span
          v-if="tab.id === 'assignments' && pendingBadge > 0"
          class="ls-app__badge"
          :title="t('learningSpace.pendingBadge', { n: pendingBadge })"
        >
          {{ pendingBadge > 99 ? '99+' : pendingBadge }}
        </span>
      </button>
    </nav>

    <nav
      v-else
      class="ls-app__tabs"
      role="tablist"
    >
      <button
        v-for="tab in studentTabs"
        :key="tab.id"
        type="button"
        role="tab"
        class="ls-app__tab"
        :class="{ 'ls-app__tab--active': studentTab === tab.id }"
        :aria-selected="studentTab === tab.id"
        @click="emit('update:studentTab', tab.id)"
      >
        <component
          :is="tab.icon"
          :size="15"
          stroke-width="2"
        />
        <span class="ls-app__tab-text">{{ t(tab.labelKey) }}</span>
        <span
          v-if="tab.id === 'assignments' && pendingBadge > 0"
          class="ls-app__badge"
          :title="t('learningSpace.todoBadge', { n: pendingBadge })"
        >
          {{ pendingBadge > 99 ? '99+' : pendingBadge }}
        </span>
      </button>
    </nav>
    </div>
  </header>
</template>
