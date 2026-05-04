<script setup lang="ts">
/**
 * MindGraphContainer - MindGraph mode content area
 * Shows diagram type selection and discovery gallery
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import {
  ElAvatar,
  ElButton,
  ElDivider,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
} from 'element-plus'

import { Upload } from '@element-plus/icons-vue'

import { Check, Globe, PanelLeftOpen } from 'lucide-vue-next'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import { useLanguage } from '@/composables'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { useAuthStore, useUIStore } from '@/stores'
import { useLiveTranslationStore } from '@/stores/liveTranslation'
import { TRANSLATE_LANGUAGES } from '@/utils/translateLanguages'

import DiagramTemplateInput from './DiagramTemplateInput.vue'
import DiagramTypeGrid from './DiagramTypeGrid.vue'
import DiscoveryGallery from './DiscoveryGallery.vue'
import InternationalLanding from './InternationalLanding.vue'
import MindGraphCollabPanel from './MindGraphCollabPanel.vue'
import MindGraphLanguageSwitcher from './MindGraphLanguageSwitcher.vue'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()
const { triggerImport } = useDiagramImport()
const authStore = useAuthStore()
const uiStore = useUIStore()
const liveTranslationStore = useLiveTranslationStore()
const {
  enabled: translationOn,
  connecting: translationConnecting,
  targetLanguage: translationTargetLang,
} = storeToRefs(liveTranslationStore)

function handleTranslateCommand(command: string): void {
  if (command === '__toggle__') {
    liveTranslationStore.toggle()
  } else {
    liveTranslationStore.setTargetLanguage(command)
  }
}

const username = computed(() => authStore.user?.username || '')

const collabPanelRef = ref<InstanceType<typeof MindGraphCollabPanel> | null>(null)

// Handle join_workshop query parameter (from QR code scan)
onMounted(() => {
  const joinWorkshopCode = route.query.join_workshop as string | undefined
  if (joinWorkshopCode) {
    const newQuery = { ...route.query }
    delete newQuery.join_workshop
    router.replace({ query: newQuery })
    collabPanelRef.value?.prefillAndAutoJoin(joinWorkshopCode)
  }
})
</script>

<template>
  <InternationalLanding v-if="uiStore.uiVersion === 'international'" />
  <div
    v-else
    class="mindgraph-container relative flex flex-col h-full"
  >
    <ElButton
      v-if="uiStore.sidebarCollapsed"
      text
      circle
      size="small"
      class="mindgraph-sidebar-toggle mindgraph-sidebar-toggle--floating"
      :title="t('sidebar.expandSidebar')"
      :aria-label="t('sidebar.expandSidebar')"
      @click="uiStore.toggleSidebar()"
    >
      <PanelLeftOpen class="w-[18px] h-[18px]" />
    </ElButton>
    <!-- Header — title centered; actions anchored right -->
    <header
      class="relative h-14 px-4 flex items-center justify-center bg-white border-b border-gray-200"
    >
      <h1 class="text-sm font-semibold text-gray-800">MindGraph</h1>
      <div class="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
        <ElButton
          class="import-btn"
          size="small"
          :icon="Upload"
          @click="triggerImport"
        >
          {{ t('mindgraphLanding.import') }}
        </ElButton>
        <!-- Buddy icon: opens inline collab panel (within-org or cross-org) -->
        <MindGraphCollabPanel ref="collabPanelRef" />
        <MindGraphLanguageSwitcher variant="header" />
        <ElDropdown
          v-if="authStore.isAdmin"
          trigger="click"
          placement="bottom-end"
          popper-class="mindgraph-translate-popper"
          class="mindgraph-translate-btn"
          @command="handleTranslateCommand"
        >
          <ElButton
            size="small"
            :loading="translationConnecting"
            :type="translationOn ? 'primary' : 'default'"
            :aria-pressed="translationOn"
            :aria-label="t('canvas.translation.aria')"
            class="mindgraph-translate-btn__trigger"
          >
            <Globe class="w-[17px] h-[17px] shrink-0" />
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu class="max-h-[min(420px,70vh)] overflow-y-auto">
              <ElDropdownItem command="__toggle__">
                <span class="translate-lang-row">
                  <span class="translate-lang-label">
                    {{
                      translationOn ? t('canvas.translation.stop') : t('canvas.translation.start')
                    }}
                  </span>
                </span>
              </ElDropdownItem>
              <ElDivider style="margin: 4px 0" />
              <ElDropdownItem
                v-for="lang in TRANSLATE_LANGUAGES"
                :key="lang.code"
                :command="lang.code"
              >
                <span class="translate-lang-row">
                  <span
                    class="translate-lang-label"
                    dir="auto"
                    >{{ lang.label }}</span
                  >
                  <Check
                    v-if="translationTargetLang === lang.code"
                    class="translate-lang-check w-4 h-4 shrink-0 opacity-70"
                    aria-hidden="true"
                  />
                </span>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </header>

    <!-- Scrollable content area -->
    <div class="flex-1 min-h-0 overflow-y-auto">
      <div class="p-5 w-[70%] mx-auto pb-8">
        <!-- Welcome header - above input -->
        <div class="flex flex-col items-center justify-center mb-8">
          <div class="mindgraph-logo-wrapper">
            <div class="mindgraph-logo-inner">
              <ElAvatar
                :src="mindgraphLogo"
                alt="MindGraph"
                :size="96"
                class="mindgraph-logo"
              />
            </div>
          </div>
          <div class="text-lg text-gray-600">
            {{ t('mindgraphLanding.welcome', { username }) }}
          </div>
        </div>

        <!-- Template input -->
        <DiagramTemplateInput />

        <!-- Diagram type grid -->
        <div class="mt-6">
          <DiagramTypeGrid />
        </div>

        <!-- Discovery gallery -->
        <DiscoveryGallery />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Translate button — stone tone when inactive, primary when active */
.mindgraph-translate-btn__trigger.el-button--default {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
}

/* Centered label with checkmark in the gutter */
.translate-lang-row {
  position: relative;
  display: block;
  box-sizing: border-box;
  width: 100%;
  padding: 5px 20px;
  min-height: 1.35em;
}

.translate-lang-label {
  display: block;
  width: 100%;
  text-align: center;
}

.translate-lang-check {
  position: absolute;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
}

@property --rainbow-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.mindgraph-logo-wrapper {
  position: relative;
  width: 104px;
  height: 104px;
  border-radius: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}

.mindgraph-logo-wrapper::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 20px;
  padding: 4px;
  --rainbow-angle: 0deg;
  /* Swiss design palette: stone tones + primary blue accent */
  background: conic-gradient(
    from var(--rainbow-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 45deg,
    #a8a29e 90deg,
    #409eff 135deg,
    #66b1ff 180deg,
    #409eff 225deg,
    #78716c 270deg,
    #d6d3d1 315deg,
    #e7e5e4 360deg
  );
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: rainbow-travel 2.5s linear infinite;
}

@keyframes rainbow-travel {
  to {
    --rainbow-angle: 360deg;
  }
}

.mindgraph-logo-inner {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--mg-bg-primary, #fff);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.mindgraph-logo {
  border-radius: 16px;
}

.mindgraph-logo :deep(img) {
  object-fit: cover;
}

/* Import button - Swiss Design style */
.import-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

.mindgraph-sidebar-toggle {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
}

.mindgraph-sidebar-toggle--floating {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 20;
}
</style>

<!-- Teleported translate dropdown — width lives on popper, not scoped subtree -->
<style>
.mindgraph-translate-popper.el-popper {
  width: min(180px, calc(100vw - 24px)) !important;
  max-width: min(180px, calc(100vw - 24px)) !important;
  box-sizing: border-box !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

.mindgraph-translate-popper .el-dropdown-menu {
  width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  scrollbar-gutter: stable;
}

.mindgraph-translate-popper .el-dropdown-menu__item {
  box-sizing: border-box;
  width: 100%;
  padding: 7px 14px !important;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  letter-spacing: 0.01em;
  border-radius: 6px;
  transition:
    background 0.12s,
    color 0.12s;
}

.mindgraph-translate-popper .el-dropdown-menu__item:hover,
.mindgraph-translate-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917;
}

.mindgraph-translate-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

/* Centered label + gutter checkmark — padding comes from the item */
.mindgraph-translate-popper .translate-lang-row {
  box-sizing: border-box;
  width: 100%;
  padding: 0;
  overflow: hidden;
}
</style>
