<script setup lang="ts">
/**
 * Auth Layout - Centered card layout for login/auth pages
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { Moon, Sunny } from '@element-plus/icons-vue'

import { toolbarShortForUiCode } from '@/i18n/locales'
import { useUIStore } from '@/stores'

const route = useRoute()
const uiStore = useUIStore()

/** `/auth`: no brand row, no manual language control — locale comes from browser on that page. */
const authLayoutMinimal = computed(() => route.meta.authLayoutMinimal === true)

/** `/auth`: same animated canvas as international landing (gallery section). */
const authMinimalGreyClass = 'auth-layout--minimal auth-layout--landing-bg select-none'

/** Beijing MIIT ICP filing (same as `MainLayout`). */
const icpRegistrationNumber = '京ICP备2025126228号'
</script>

<template>
  <div
    class="auth-layout min-h-screen flex flex-col"
    :class="
      authLayoutMinimal
        ? authMinimalGreyClass
        : 'bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900'
    "
  >
    <!-- Header (hidden on /auth — Swiss minimal route) -->
    <header
      v-if="!authLayoutMinimal"
      class="absolute top-0 left-0 right-0 h-14 px-6 flex items-center justify-between z-10"
    >
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-sm">MG</span>
        </div>
        <span class="text-white/80 font-medium">MindGraph Pro</span>
      </div>

      <div class="flex items-center gap-2">
        <el-button
          circle
          class="!bg-white/10 !border-white/20 !text-white hover:!bg-white/20"
          @click="uiStore.toggleTheme"
        >
          <el-icon>
            <Sunny v-if="uiStore.isDark" />
            <Moon v-else />
          </el-icon>
        </el-button>

        <el-button
          circle
          class="!bg-white/10 !border-white/20 !text-white hover:!bg-white/20"
          @click="uiStore.toggleLanguage"
        >
          {{ toolbarShortForUiCode(uiStore.language) }}
        </el-button>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 flex items-center justify-center p-4">
      <div class="auth-card w-full max-w-md">
        <!-- Background decorations (classic auth only) -->
        <template v-if="!authLayoutMinimal">
          <div
            class="absolute -top-20 -right-20 w-40 h-40 bg-primary-500/20 rounded-full blur-3xl"
          />
          <div
            class="absolute -bottom-20 -left-20 w-40 h-40 bg-indigo-500/20 rounded-full blur-3xl"
          />
        </template>

        <!-- Card Content: frosted glass for legacy glass routes; flat Swiss neutral for /auth -->
        <div
          class="relative rounded-2xl"
          :class="
            authLayoutMinimal
              ? 'bg-transparent p-0 shadow-none border-0'
              : 'bg-white/10 backdrop-blur-xl border border-white/20 p-8 shadow-2xl'
          "
        >
          <slot />
        </div>
      </div>
    </main>

    <footer
      class="py-4 px-4 text-center text-sm"
      :class="authLayoutMinimal ? 'text-stone-400' : 'text-white/40'"
    >
      <template v-if="authLayoutMinimal">
        <p class="text-xs text-stone-400">
          {{ icpRegistrationNumber }}
        </p>
      </template>
      <template v-else>
        <p>MindGraph Pro - Intelligent Diagram Creation</p>
      </template>
    </footer>
  </div>
</template>

<style scoped>
.auth-layout {
  position: relative;
  overflow: hidden;
}

.auth-card {
  position: relative;
}

/* Minimal /auth: animated canvas (mirrors `InternationalLanding` / gallery). */
.auth-layout--minimal.auth-layout--landing-bg {
  isolation: isolate;
  color-scheme: light;
  background-color: rgb(248 250 252);
  background-image: linear-gradient(
    97deg,
    transparent 0%,
    transparent 32%,
    rgba(148, 163, 184, 0.32) 38%,
    rgba(255, 255, 255, 0.98) 46%,
    rgba(102, 126, 234, 0.26) 49.5%,
    rgba(237, 233, 254, 0.75) 50%,
    rgba(118, 75, 162, 0.12) 50.8%,
    rgba(248, 250, 252, 0.95) 53%,
    rgba(100, 116, 139, 0.28) 61%,
    transparent 72%,
    transparent 100%
  );
  background-size: 300% 100%;
  background-position: 0% 50%;
  background-repeat: no-repeat;
  animation: authLandingSheen 19s linear infinite;
  animation-delay: -6s;
}

.auth-layout--minimal.auth-layout--landing-bg::before,
.auth-layout--minimal.auth-layout--landing-bg::after {
  content: '';
  position: absolute;
  pointer-events: none;
  z-index: 0;
}

.auth-layout--minimal.auth-layout--landing-bg::before {
  top: -32%;
  left: -52%;
  width: 205%;
  height: 195%;
  background: linear-gradient(
    104deg,
    transparent 0%,
    transparent 26%,
    rgba(148, 163, 184, 0.14) 38%,
    rgba(102, 126, 234, 0.12) 50%,
    rgba(226, 232, 240, 0.78) 51%,
    rgba(118, 75, 162, 0.1) 52%,
    rgba(148, 163, 184, 0.16) 62%,
    transparent 100%
  );
  filter: blur(11px);
  transform: translateX(-6%) rotate(1.25deg);
  animation: authLandingWindPrimary 28s linear infinite;
  animation-delay: -10s;
}

.auth-layout--minimal.auth-layout--landing-bg::after {
  top: -20%;
  right: -72%;
  width: 190%;
  height: 180%;
  background: linear-gradient(
    -68deg,
    transparent 0%,
    rgba(241, 245, 249, 0.95) 40%,
    rgba(255, 255, 255, 0.75) 49%,
    rgba(102, 126, 234, 0.1) 51%,
    rgba(100, 116, 139, 0.16) 58%,
    transparent 100%
  );
  filter: blur(9px);
  opacity: 1;
  animation: authLandingWindSecondary 36s linear infinite;
  animation-delay: -18s;
}

.auth-layout--minimal.auth-layout--landing-bg > main,
.auth-layout--minimal.auth-layout--landing-bg > footer {
  position: relative;
  z-index: 1;
}

@keyframes authLandingSheen {
  0%,
  100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

@keyframes authLandingWindPrimary {
  0%,
  100% {
    transform: translateX(-6%) translateY(0) rotate(1.25deg);
  }
  50% {
    transform: translateX(38%) translateY(4%) rotate(0.9deg);
  }
}

@keyframes authLandingWindSecondary {
  0%,
  100% {
    transform: translateX(8%) translateY(-5%);
  }
  50% {
    transform: translateX(-32%) translateY(7%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-layout--minimal.auth-layout--landing-bg {
    animation: none;
    background-position: 50% 50%;
  }

  .auth-layout--minimal.auth-layout--landing-bg::before,
  .auth-layout--minimal.auth-layout--landing-bg::after {
    animation: none;
  }
}

/* Override Element Plus styles for legacy login/demo auth pages (dark glass card) */
.auth-layout:not(.auth-layout--minimal) :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: none;
}

.auth-layout:not(.auth-layout--minimal) :deep(.el-input__wrapper:hover) {
  border-color: rgba(255, 255, 255, 0.4);
}

.auth-layout:not(.auth-layout--minimal) :deep(.el-input__wrapper.is-focus) {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.auth-layout:not(.auth-layout--minimal) :deep(.el-input__inner) {
  color: white;
}

.auth-layout:not(.auth-layout--minimal) :deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.5);
}

.auth-layout:not(.auth-layout--minimal) :deep(.el-form-item__label) {
  color: rgba(255, 255, 255, 0.8);
}
</style>
