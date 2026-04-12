<script setup lang="ts">
/**
 * IntlModuleGrid - Grid menu for International UI.
 * Shows available modules in a popover grid, replacing sidebar navigation.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  ChatDotRound,
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

import { LayoutGrid, MessageSquare, Settings, Watch } from 'lucide-vue-next'

import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { userCanAccessWorkshopChat } from '@/utils/workshopAccess'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useLanguage()
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
  workshopChatPreviewOrgIds,
  featureOrgAccess,
} = useFeatureFlags()

const gridOpen = ref(false)

interface ModuleItem {
  key: string
  labelKey: string
  route: string
  icon: unknown
  visible: boolean
}

const isAuthenticated = computed(() => authStore.isAuthenticated)
const isAdmin = computed(() => authStore.isAdmin)
const isAdminOrManager = computed(() => authStore.isAdminOrManager)
const hasOrg = computed(() => isAuthenticated.value && !!authStore.user?.schoolId)

const canWorkshop = computed(() => {
  if (!featureWorkshopChat.value) return false
  const entry = (featureOrgAccess.value as Record<string, unknown>).feature_workshop_chat
  return userCanAccessWorkshopChat(
    isAdminOrManager.value,
    authStore.user?.schoolId,
    authStore.user?.id,
    workshopChatPreviewOrgIds.value,
    entry as Parameters<typeof userCanAccessWorkshopChat>[4]
  )
})

const modules = computed<ModuleItem[]>(() => [
  {
    key: 'knowledge-space',
    labelKey: 'sidebar.knowledgeSpace',
    route: '/knowledge-space',
    icon: Document,
    visible: isAuthenticated.value && featureKnowledgeSpace.value,
  },
  {
    key: 'askonce',
    labelKey: 'askonce.title',
    route: '/askonce',
    icon: MagicStick,
    visible: featureAskOnce.value,
  },
  {
    key: 'debateverse',
    labelKey: 'sidebar.debateverse',
    route: '/debateverse',
    icon: ChatDotRound,
    visible: featureDebateverse.value,
  },
  {
    key: 'school-zone',
    labelKey: 'sidebar.schoolZone',
    route: '/school-zone',
    icon: OfficeBuilding,
    visible: hasOrg.value && featureSchoolZone.value,
  },
  {
    key: 'template',
    labelKey: 'sidebar.templateResources',
    route: '/template',
    icon: Files,
    visible: featureTemplate.value,
  },
  {
    key: 'course',
    labelKey: 'sidebar.courses',
    route: '/course',
    icon: VideoPlay,
    visible: featureCourse.value,
  },
  {
    key: 'community',
    labelKey: 'sidebar.community',
    route: '/community',
    icon: Share,
    visible: featureCommunity.value,
  },
  {
    key: 'library',
    labelKey: 'sidebar.library',
    route: '/library',
    icon: Reading,
    visible: featureLibrary.value,
  },
  {
    key: 'chunk-test',
    labelKey: 'sidebar.chunkTest',
    route: '/chunk-test',
    icon: Tools,
    visible: isAuthenticated.value && featureRagChunkTest.value,
  },
  {
    key: 'workshop-chat',
    labelKey: 'workshop.title',
    route: '/workshop-chat',
    icon: MessageSquare,
    visible: canWorkshop.value,
  },
  {
    key: 'smart-response',
    labelKey: 'sidebar.smartResponse',
    route: '/smart-response',
    icon: Watch,
    visible: isAdminOrManager.value && featureSmartResponse.value,
  },
  {
    key: 'teacher-usage',
    labelKey: 'sidebar.teacherUsage',
    route: '/teacher-usage',
    icon: TrendCharts,
    visible: isAdmin.value && featureTeacherUsage.value,
  },
  {
    key: 'school-dashboard',
    labelKey: 'admin.schoolDashboard',
    route: '/school-dashboard',
    icon: OfficeBuilding,
    visible: isAdminOrManager.value,
  },
  {
    key: 'gewe',
    labelKey: 'Gewe',
    route: '/gewe',
    icon: ChatDotRound,
    visible: isAdmin.value && featureGewe.value,
  },
  {
    key: 'admin',
    labelKey: 'admin.title',
    route: '/admin',
    icon: Settings,
    visible: isAdmin.value,
  },
])

const visibleModules = computed(() => modules.value.filter((m) => m.visible))

function goTo(route: string) {
  gridOpen.value = false
  router.push(route)
}
</script>

<template>
  <el-popover
    v-model:visible="gridOpen"
    placement="bottom-end"
    trigger="click"
    :width="320"
    popper-class="intl-module-grid-popper"
  >
    <template #reference>
      <slot name="reference">
        <button
          type="button"
          class="intl-grid-btn"
          :title="t('landing.international.modules')"
        >
          <LayoutGrid class="w-5 h-5" />
        </button>
      </slot>
    </template>
    <div class="intl-module-grid">
      <div
        v-for="m in visibleModules"
        :key="m.key"
        class="intl-module-tile"
        @click="goTo(m.route)"
      >
        <div class="intl-module-icon">
          <component
            :is="m.icon"
            class="w-6 h-6"
          />
        </div>
        <span class="intl-module-label">{{ m.key === 'gewe' ? 'Gewe' : t(m.labelKey) }}</span>
      </div>
    </div>
  </el-popover>
</template>

<style scoped>
.intl-grid-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--el-text-color-regular, #57534e);
  transition:
    background-color 0.2s,
    color 0.2s;
}

.intl-grid-btn:hover {
  background: var(--el-fill-color-light, #f5f5f4);
  color: var(--el-text-color-primary, #1c1917);
}

.intl-module-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
}

.intl-module-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 6px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background-color 0.15s;
  user-select: none;
}

.intl-module-tile:hover {
  background-color: var(--el-fill-color-light, #f5f5f4);
}

.intl-module-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--el-fill-color-lighter, #fafaf9);
  color: var(--el-text-color-regular, #57534e);
  transition:
    background-color 0.15s,
    color 0.15s;
}

.intl-module-tile:hover .intl-module-icon {
  background: #667eea;
  color: #fff;
}

.intl-module-label {
  font-size: 12px;
  line-height: 1.3;
  text-align: center;
  color: var(--el-text-color-regular, #57534e);
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
