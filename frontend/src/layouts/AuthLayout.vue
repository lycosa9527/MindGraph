<script setup lang="ts">
/**
 * Auth Layout - Centered card layout for login/auth pages
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { Moon, Sunny } from '@element-plus/icons-vue'

import { useUIStore } from '@/stores'

const route = useRoute()
const uiStore = useUIStore()

/** `/auth`: no brand row, no manual language control — locale comes from browser on that page. */
const authLayoutMinimal = computed(() => route.meta.authLayoutMinimal === true)

/** Match MindGraph page shell (`bg-gray-50`) for international UI; CN keeps neutral stone. */
const authMinimalGreyClass = computed(() =>
  uiStore.uiVersion === 'international'
    ? 'auth-layout--minimal-intl bg-gray-50'
    : 'auth-layout--minimal bg-stone-200'
)

/** Beijing MIIT ICP filing (same as `MainLayout`). */
const icpRegistrationNumber = '京ICP备2025126228号'
</script>

<template>
  <div
    class="auth-layout min-h-screen flex flex-col"
    :class="
      authLayoutMinimal
        ? `${authMinimalGreyClass} select-none`
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
          {{ uiStore.language === 'zh' ? 'EN' : '中' }}
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

/* Minimal /auth (CN): neutral stone; LoginModal uses `lightBackdrop` (no scrim). */
.auth-layout--minimal {
  background-color: rgb(231 229 228) !important; /* stone-200 */
  color-scheme: light;
}

/* Minimal /auth (international): same grey as MindGraphPage shell */
.auth-layout--minimal-intl {
  background-color: rgb(249 250 251) !important; /* gray-50 */
  color-scheme: light;
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
