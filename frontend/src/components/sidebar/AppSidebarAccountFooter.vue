<script setup lang="ts">
/**
 * Sidebar bottom: login CTA or user menu with account actions.
 */
import { computed, inject, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  ChevronDown,
  Coins,
  Flame,
  Gift,
  Languages,
  Link2,
  LogIn,
  LogOut,
  ScrollText,
  Share2,
  Star,
  Upload,
  UserRound,
} from '@lucide/vue'

import QuickRegisterModal from '@/components/mindgraph/QuickRegisterModal.vue'
import SidebarQuoteMarquee from '@/components/sidebar/SidebarQuoteMarquee.vue'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { appSidebarInjectionKey } from '@/composables/sidebar/useAppSidebar'
import { useSidebarPhilosophyQuote } from '@/composables/sidebar/useSidebarPhilosophyQuote'
import { useSidebarThinkingCoinTaskPromo } from '@/composables/sidebar/useSidebarThinkingCoinTaskPromo'
import { usePwaInstall } from '@/composables/usePwaInstall'
import { isMindGraphLandingPath } from '@/utils/canvasBackNavigation'

const sidebarCtx = inject(appSidebarInjectionKey)
if (!sidebarCtx) {
  throw new Error('AppSidebarAccountFooter must be used inside AppSidebar')
}
const s = reactive(sidebarCtx)
const route = useRoute()
const showShareSiteModal = ref(false)
const { triggerImport } = useDiagramImport()
const showMindGraphGalleryImport = computed(() => isMindGraphLandingPath(route.path))
const { showPwaInstall, handlePwaInstall } = usePwaInstall((key) => s.t(key))
const { quote } = useSidebarPhilosophyQuote()
const { promoTitle, promoReward, taskPromoKey, showInviteAccent } = useSidebarThinkingCoinTaskPromo(
  sidebarCtx.thinkingCoinEarnTasks,
  () => s.t('thinkingCoins.invitePromo')
)

onMounted(() => {
  if (sidebarCtx.thinkingCoinsEligible.value) {
    void sidebarCtx.refreshThinkingCoinEarnTasks()
  }
})
</script>

<template>
  <div class="border-t border-stone-200 relative">
    <!-- Not authenticated: Show login button -->
    <template v-if="!s.isAuthenticated">
      <div :class="s.isCollapsed ? 'p-2 flex flex-col gap-2' : 'p-4 flex flex-col gap-2'">
        <el-button
          v-if="!s.isCollapsed"
          type="primary"
          class="login-btn w-full"
          @click="s.openLoginModal"
        >
          {{ s.t('auth.loginRegister') }}
        </el-button>
        <el-button
          v-else
          type="primary"
          circle
          class="login-btn-collapsed w-full"
          @click="s.openLoginModal"
        >
          <LogIn class="w-4 h-4" />
        </el-button>
      </div>
    </template>

    <!-- Authenticated: Show user info with dropdown -->
    <template v-else>
      <!-- Thinking coins widget (trial teachers only) -->
      <div
        v-if="s.thinkingCoinsEligible"
        :class="s.isCollapsed ? 'px-2 pt-2' : 'px-2.5 pt-2.5 pb-2'"
      >
        <div
          v-if="!s.isCollapsed"
          class="tc-sidebar-widget"
        >
          <div class="flex items-center justify-between gap-2.5">
            <button
              type="button"
              class="tc-balance-label min-w-0"
              @click="s.openThinkingCoinsUpgrade()"
            >
              <span class="leading-tight truncate">
                <span class="text-xs font-medium text-stone-600">{{ s.t('thinkingCoins.balanceUnit') }}:</span>
                <span class="text-base font-bold tabular-nums tracking-tight text-stone-900">
                  {{ s.thinkingCoinsBalanceFormatted }}
                </span>
              </span>
            </button>
            <div class="tc-upgrade-orbit shrink-0">
              <span
                class="tc-upgrade-orbit__ring"
                aria-hidden="true"
              />
              <button
                type="button"
                class="tc-sidebar-upgrade"
                @click="s.openThinkingCoinsUpgrade()"
              >
                <Star class="h-3 w-3 fill-current" />
                {{ s.t('thinkingCoins.upgrade') }}
              </button>
            </div>
          </div>
          <button
            type="button"
            class="tc-sidebar-promo mt-2.5 flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left transition hover:brightness-[0.98]"
            @click="s.openThinkingCoinsUpgrade()"
          >
            <Gift class="h-4 w-4 shrink-0 text-orange-500" />
            <div class="tc-task-promo-viewport min-w-0 flex-1">
              <Transition
                name="tc-task-fade"
                mode="out-in"
              >
                <span
                  :key="taskPromoKey"
                  class="tc-task-promo-line block truncate text-xs font-medium text-stone-700"
                >
                  {{ promoTitle }}
                </span>
              </Transition>
            </div>
            <Transition
              name="tc-task-fade"
              mode="out-in"
            >
              <Flame
                v-if="showInviteAccent"
                :key="`${taskPromoKey}-flame`"
                class="h-4 w-4 shrink-0 text-orange-500"
              />
              <span
                v-else
                :key="`${taskPromoKey}-reward`"
                class="shrink-0 text-xs font-bold tabular-nums text-orange-500"
              >
                +{{ promoReward }}
              </span>
            </Transition>
          </button>
        </div>
        <el-tooltip
          v-else
          :content="`${s.t('thinkingCoins.balanceUnit')}: ${s.thinkingCoinsBalanceFormatted}`"
          placement="right"
        >
          <button
            type="button"
            class="flex w-full items-center justify-center rounded-xl bg-white p-2.5 shadow-[0_1px_2px_rgba(28,25,23,0.05),0_4px_14px_rgba(28,25,23,0.06)] transition-colors hover:bg-amber-50"
            @click="s.openThinkingCoinsUpgrade()"
          >
            <Coins class="h-4 w-4 text-amber-600" />
          </button>
        </el-tooltip>
      </div>

      <el-dropdown
        v-if="!s.isCollapsed"
        trigger="click"
        placement="top-end"
        popper-class="user-dropdown-popper"
        :popper-options="{
          modifiers: [
            { name: 'offset', options: { offset: [0, 8] } },
            { name: 'flip', options: { fallbackPlacements: [] } },
          ],
        }"
        class="user-dropdown w-full"
      >
        <div
          class="user-dropdown-trigger flex items-center justify-between cursor-pointer hover:bg-[#f5f5f4] transition-colors px-4 py-3 w-full"
        >
          <div class="flex items-center min-w-0 flex-1">
            <el-badge
              :value="0"
              :hidden="true"
              class="shrink-0"
            >
              <el-avatar
                :size="40"
                class="bg-stone-200 text-2xl mg-user-avatar-emoji"
              >
                {{ s.userAvatar }}
              </el-avatar>
            </el-badge>
            <div class="ml-3 min-w-0 flex-1">
              <div class="flex items-center gap-1.5 min-w-0">
                <div class="text-sm font-medium text-stone-900 truncate leading-tight min-w-0">
                  {{ s.userName }}
                </div>
                <span
                  v-if="s.userRolePill"
                  class="role-pill shrink-0 inline-flex items-center rounded-full border px-1.5 py-0 text-[10px] font-medium leading-4"
                  :class="[
                    s.userRolePill.bgClass,
                    s.userRolePill.textClass,
                    s.userRolePill.borderClass,
                  ]"
                >
                  {{ s.userRolePill.label }}
                </span>
              </div>
              <SidebarQuoteMarquee
                v-if="quote"
                :text="quote.text"
                :author="quote.author"
              />
            </div>
          </div>
          <ChevronDown class="w-4 h-4 text-stone-400 shrink-0 ml-2" />
        </div>
        <template #dropdown>
          <el-dropdown-menu class="user-dropdown-menu max-h-[min(420px,70vh)] overflow-y-auto">
            <el-dropdown-item
              v-if="showMindGraphGalleryImport"
              @click="triggerImport"
            >
              <Upload class="w-4 h-4 mr-2" />
              {{ s.t('mindgraphLanding.import') }}
            </el-dropdown-item>
            <el-dropdown-item
              v-if="s.isAdminOrManager"
              @click="showShareSiteModal = true"
            >
              <Share2 class="w-4 h-4 mr-2" />
              {{ s.t('landing.international.shareSite') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              @click="s.openLanguageSettingsModal"
            >
              <Languages class="w-4 h-4 mr-2" />
              {{ s.t('sidebar.languageSettings') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openAccountModal">
              <UserRound class="w-4 h-4 mr-2" />
              {{ s.t('auth.accountInfo') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openUpdateLogModal">
              <ScrollText class="w-4 h-4 mr-2" />
              {{ s.t('auth.updateLog') }}
            </el-dropdown-item>
            <el-dropdown-item
              v-if="showPwaInstall"
              @click="handlePwaInstall"
            >
              <Link2 class="w-4 h-4 mr-2" />
              {{ s.t('auth.downloadDesktopShortcut') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              class="user-dropdown-item--logout"
              @click="s.handleLogout"
            >
              <LogOut class="w-4 h-4 mr-2" />
              {{ s.t('auth.logout') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- Collapsed mode: show avatar button with dropdown -->
      <el-dropdown
        v-else
        trigger="click"
        placement="top-end"
        popper-class="user-dropdown-popper"
        :popper-options="{
          modifiers: [{ name: 'offset', options: { offset: [0, 8] } }],
        }"
        class="user-dropdown-collapsed"
      >
        <el-badge
          :value="0"
          :hidden="true"
        >
          <el-button
            text
            circle
            class="toggle-btn"
          >
            <el-avatar
              :size="32"
              class="bg-stone-200 text-xl mg-user-avatar-emoji"
            >
              {{ s.userAvatar }}
            </el-avatar>
          </el-button>
        </el-badge>
        <template #dropdown>
          <el-dropdown-menu class="user-dropdown-menu max-h-[min(420px,70vh)] overflow-y-auto">
            <el-dropdown-item
              v-if="showMindGraphGalleryImport"
              @click="triggerImport"
            >
              <Upload class="w-4 h-4 mr-2" />
              {{ s.t('mindgraphLanding.import') }}
            </el-dropdown-item>
            <el-dropdown-item
              v-if="s.isAdminOrManager"
              @click="showShareSiteModal = true"
            >
              <Share2 class="w-4 h-4 mr-2" />
              {{ s.t('landing.international.shareSite') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              @click="s.openLanguageSettingsModal"
            >
              <Languages class="w-4 h-4 mr-2" />
              {{ s.t('sidebar.languageSettings') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openAccountModal">
              <UserRound class="w-4 h-4 mr-2" />
              {{ s.t('auth.accountInfo') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openUpdateLogModal">
              <ScrollText class="w-4 h-4 mr-2" />
              {{ s.t('auth.updateLog') }}
            </el-dropdown-item>
            <el-dropdown-item
              v-if="showPwaInstall"
              @click="handlePwaInstall"
            >
              <Link2 class="w-4 h-4 mr-2" />
              {{ s.t('auth.downloadDesktopShortcut') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              class="user-dropdown-item--logout"
              @click="s.handleLogout"
            >
              <LogOut class="w-4 h-4 mr-2" />
              {{ s.t('auth.logout') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>

    <QuickRegisterModal v-model="showShareSiteModal" />
  </div>
</template>

<style scoped>
/* Login button - Swiss Design style */
.login-btn {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  --el-button-active-bg-color: #0c0a09;
  --el-button-active-border-color: #0c0a09;
  font-weight: 500;
}

.login-btn-collapsed {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
}

.toggle-btn {
  --el-button-text-color: #78716c;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #e7e5e4;
}

/* Avatar styling - Swiss Design style */
.user-dropdown :deep(.el-avatar) {
  --el-avatar-bg-color: #e7e5e4;
  color: #1c1917;
  font-weight: normal;
}

.user-dropdown-collapsed :deep(.el-avatar) {
  --el-avatar-bg-color: #e7e5e4;
  color: #1c1917;
  font-weight: normal;
}

.user-dropdown {
  width: 100%;
}

.tc-sidebar-widget {
  min-width: 0;
  padding: 0.625rem 0.75rem;
  border-radius: 1rem;
  background: #ffffff;
  box-shadow:
    0 1px 2px rgba(28, 25, 23, 0.05),
    0 4px 14px rgba(28, 25, 23, 0.06);
}

.tc-balance-label {
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

.tc-balance-label:focus-visible {
  outline: 2px solid #d6d3d1;
  outline-offset: 2px;
  border-radius: 6px;
}

.tc-sidebar-promo {
  background: #fff8eb;
  border: none;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

.tc-sidebar-promo:focus-visible {
  outline: 2px solid #fcd34d;
  outline-offset: 1px;
}

.tc-upgrade-orbit {
  position: relative;
  display: inline-flex;
  padding: 2px;
  border-radius: 9999px;
  overflow: hidden;
  isolation: isolate;
}

.tc-upgrade-orbit__ring {
  position: absolute;
  inset: -120%;
  z-index: 0;
  background: conic-gradient(
    from 0deg,
    #ef4444 0deg,
    #f97316 52deg,
    #eab308 104deg,
    #22c55e 156deg,
    #06b6d4 208deg,
    #3b82f6 260deg,
    #a855f7 312deg,
    #ef4444 360deg
  );
  animation: tc-upgrade-rainbow-travel 2.8s linear infinite;
}

.tc-sidebar-upgrade {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border: none;
  border-radius: 9999px;
  padding: 0.3125rem 0.6875rem;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  color: #fff;
  background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%);
  box-shadow: 0 1px 2px rgba(234, 88, 12, 0.2);
  cursor: pointer;
  transition:
    transform 0.12s ease,
    box-shadow 0.12s ease;
}

.tc-upgrade-orbit:hover .tc-sidebar-upgrade {
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(234, 88, 12, 0.25);
}

@keyframes tc-upgrade-rainbow-travel {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .tc-upgrade-orbit__ring {
    animation: none;
    inset: 0;
    background: linear-gradient(90deg, #f59e0b, #ea580c);
  }
}

.tc-task-promo-viewport {
  position: relative;
  height: 1.125rem;
  overflow: hidden;
}

.tc-task-promo-line {
  line-height: 1.125rem;
}

.tc-task-fade-enter-active,
.tc-task-fade-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.28s ease;
}

.tc-task-fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.tc-task-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .tc-task-fade-enter-active,
  .tc-task-fade-leave-active {
    transition: opacity 0.12s ease;
  }

  .tc-task-fade-enter-from,
  .tc-task-fade-leave-to {
    transform: none;
  }
}
</style>

<!-- Teleported popper — Swiss (matches MindGraphLanguageSwitcher / canvas-more-apps) -->
<style>
.user-dropdown-popper.el-popper {
  box-sizing: border-box !important;
  width: max-content !important;
  max-width: min(280px, calc(100vw - 24px)) !important;
  min-width: 0 !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

.dark .user-dropdown-popper.el-popper {
  border-color: #374151 !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.25),
    0 2px 4px -2px rgba(0, 0, 0, 0.18) !important;
}

.user-dropdown-popper .el-popper__arrow {
  left: auto !important;
  right: 16px !important;
}

.user-dropdown-popper .user-dropdown-menu.el-dropdown-menu {
  width: max-content !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  scrollbar-gutter: stable;
}

.user-dropdown-popper .el-dropdown-menu__item {
  display: flex !important;
  align-items: center;
  padding: 8px 14px !important;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  border-radius: 6px;
  line-height: 1.4;
  letter-spacing: 0.01em;
  max-width: 100%;
  box-sizing: border-box;
  overflow-wrap: anywhere;
  transition:
    background 0.12s,
    color 0.12s;
}

.user-dropdown-popper .el-dropdown-menu__item:hover,
.user-dropdown-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917 !important;
}

.user-dropdown-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

.user-dropdown-popper .el-dropdown-menu__item svg {
  flex-shrink: 0;
}

.dark .user-dropdown-popper .el-dropdown-menu__item {
  color: #d6d3d1;
}

.dark .user-dropdown-popper .el-dropdown-menu__item:hover,
.dark .user-dropdown-popper .el-dropdown-menu__item:focus {
  background: #374151 !important;
  color: #f9fafb !important;
}

.dark .user-dropdown-popper .el-dropdown-menu__item:active {
  background: #4b5563 !important;
}

.user-dropdown-popper .el-dropdown-menu__item.is-divided {
  border-top: 1px solid #f3f4f6;
  margin-top: 2px;
  padding-top: 10px;
}

.dark .user-dropdown-popper .el-dropdown-menu__item.is-divided {
  border-top-color: #4b5563;
}

.user-dropdown-popper .user-dropdown-item--logout {
  color: #dc2626;
}

.user-dropdown-popper .user-dropdown-item--logout:hover,
.user-dropdown-popper .user-dropdown-item--logout:focus {
  background: #fef2f2 !important;
  color: #b91c1c !important;
}

.dark .user-dropdown-popper .user-dropdown-item--logout {
  color: #f87171;
}

.dark .user-dropdown-popper .user-dropdown-item--logout:hover,
.dark .user-dropdown-popper .user-dropdown-item--logout:focus {
  background: rgba(127, 29, 29, 0.35) !important;
  color: #fecaca !important;
}
</style>
