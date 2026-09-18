<script setup lang="ts">
/**
 * Auth Layout — split shell for `/auth`; legacy glass for other auth routes.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { Moon, Sunny } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables'
import { toolbarShortForUiCode } from '@/i18n/locales'
import { useUIStore } from '@/stores'

const route = useRoute()
const uiStore = useUIStore()
const { toggleLanguage } = useLanguage()

const authLayoutMinimal = computed(() => route.meta.authLayoutMinimal === true)
</script>

<template>
  <div
    class="auth-layout min-h-screen flex flex-col"
    :class="
      authLayoutMinimal
        ? 'auth-layout--minimal auth-layout--split select-none'
        : 'bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900'
    "
  >
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
          @click="toggleLanguage"
        >
          {{ toolbarShortForUiCode(uiStore.language) }}
        </el-button>
      </div>
    </header>

    <main
      class="flex-1 flex"
      :class="authLayoutMinimal ? 'auth-layout__main--split' : 'items-center justify-center p-4'"
    >
      <div
        class="auth-card w-full"
        :class="authLayoutMinimal ? 'auth-card--split' : 'max-w-md'"
      >
        <template v-if="!authLayoutMinimal">
          <div
            class="absolute -top-20 -right-20 w-40 h-40 bg-primary-500/20 rounded-full blur-3xl"
          />
          <div
            class="absolute -bottom-20 -left-20 w-40 h-40 bg-indigo-500/20 rounded-full blur-3xl"
          />
        </template>

        <div
          class="relative"
          :class="
            authLayoutMinimal
              ? 'h-full min-h-0 bg-transparent p-0 shadow-none border-0'
              : 'rounded-2xl bg-white/10 backdrop-blur-xl border border-white/20 p-8 shadow-2xl'
          "
        >
          <slot />
        </div>
      </div>
    </main>

    <footer
      v-if="!authLayoutMinimal"
      class="py-4 px-4 text-center text-sm text-white/40"
    >
      <p>MindGraph Pro - Intelligent Diagram Creation</p>
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

.auth-layout--minimal.auth-layout--split {
  isolation: isolate;
  color-scheme: light;
  background: #fff;
}

.auth-layout__main--split {
  min-height: 100dvh;
  align-items: stretch;
  justify-content: stretch;
  padding: 0;
}

.auth-card--split {
  max-width: none;
  height: 100%;
  min-height: 100dvh;
}

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
