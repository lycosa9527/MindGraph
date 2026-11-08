<script setup lang="ts">
/**
 * Learning Space top tabs (works beside the main app sidebar).
 */
import { computed, nextTick, ref, watch } from 'vue'
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
import { useAuthStore } from '@/stores'
import { useUIStore } from '@/stores/ui'

const props = defineProps<{
  mode: 'teacher' | 'student'
  teacherTab: TeacherTab
  studentTab: StudentTab
  tabBadge: number
  showShellSwitch?: boolean
}>()

const emit = defineEmits<{
  'update:teacherTab': [TeacherTab]
  'update:studentTab': [StudentTab]
  'update:mode': ['teacher' | 'student']
}>()

const SHELL_ROLE_TIP_KEY = 'mg.ls.shell-role-tip.v1'

const { t } = useLanguage()
const route = useRoute()
const authStore = useAuthStore()
const uiStore = useUIStore()

const showRoleTip = ref(false)

const showSidebarExpand = computed(() => uiStore.sidebarCollapsed && !route.path.startsWith('/m/'))

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

function shellRoleTipStorageKey(): string {
  const userId = authStore.user?.id?.trim()
  return userId ? `${SHELL_ROLE_TIP_KEY}:${userId}` : SHELL_ROLE_TIP_KEY
}

function hasSeenShellRoleTip(): boolean {
  try {
    return localStorage.getItem(shellRoleTipStorageKey()) === '1'
  } catch {
    return false
  }
}

function markShellRoleTipSeen(): void {
  try {
    localStorage.setItem(shellRoleTipStorageKey(), '1')
  } catch {
    /* ignore quota / private mode */
  }
}

function dismissShellRoleTip(): void {
  if (!showRoleTip.value) return
  showRoleTip.value = false
  markShellRoleTipSeen()
}

function maybeShowShellRoleTip(): void {
  if (!props.showShellSwitch || hasSeenShellRoleTip()) {
    showRoleTip.value = false
    return
  }
  showRoleTip.value = true
}

function onShellModeClick(mode: 'teacher' | 'student'): void {
  dismissShellRoleTip()
  emit('update:mode', mode)
}

watch(
  () => props.showShellSwitch,
  async (visible) => {
    if (!visible) {
      showRoleTip.value = false
      return
    }
    await nextTick()
    maybeShowShellRoleTip()
  },
  { immediate: true }
)
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
        <div class="ls-app__brand-title"><I18nText k="learningSpace.brandTitle" /></div>
      </div>
      <div
        v-if="showShellSwitch"
        class="ls-app__shell-switch-wrap"
      >
        <div
          class="ls-app__shell-switch"
          :class="{ 'ls-app__shell-switch--hint': showRoleTip }"
          role="tablist"
          :aria-label="t('learningSpace.shellRoleSwitchAria')"
        >
          <button
            type="button"
            role="tab"
            class="ls-app__tab"
            :class="{ 'ls-app__tab--active': mode === 'teacher' }"
            :aria-selected="mode === 'teacher'"
            @click="onShellModeClick('teacher')"
          >
            <I18nText k="learningSpace.modeReview" />
          </button>
          <button
            type="button"
            role="tab"
            class="ls-app__tab"
            :class="{ 'ls-app__tab--active': mode === 'student' }"
            :aria-selected="mode === 'student'"
            @click="onShellModeClick('student')"
          >
            <I18nText k="learningSpace.modeLearn" />
          </button>
        </div>
        <div
          v-if="showRoleTip"
          class="ls-app__shell-tip"
          role="status"
        >
          <p class="ls-app__shell-tip-text">
            <I18nText k="learningSpace.shellRoleTip" />
          </p>
          <button
            type="button"
            class="ls-app__shell-tip-btn"
            @click="dismissShellRoleTip"
          >
            <I18nText k="learningSpace.shellRoleTipGotIt" />
          </button>
        </div>
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
          <span class="ls-app__tab-text"><I18nText :k="tab.labelKey" /></span>
          <span
            v-if="tab.id === 'assignments' && tabBadge > 0"
            class="ls-app__badge"
            :title="t('learningSpace.assignmentBadge', { n: tabBadge })"
          >
            {{ tabBadge > 99 ? '99+' : tabBadge }}
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
          <span class="ls-app__tab-text"><I18nText :k="tab.labelKey" /></span>
          <span
            v-if="tab.id === 'assignments' && tabBadge > 0"
            class="ls-app__badge"
            :title="t('learningSpace.todoBadge', { n: tabBadge })"
          >
            {{ tabBadge > 99 ? '99+' : tabBadge }}
          </span>
        </button>
      </nav>
    </div>
  </header>
</template>
