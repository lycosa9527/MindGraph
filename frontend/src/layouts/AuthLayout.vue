<script setup lang="ts">
/**
 * Auth Layout - Centered card layout for login/auth pages
 */
import { useUIStore } from '@/stores'

const uiStore = useUIStore()
</script>

<template>
  <div
    class="auth-layout min-h-screen flex flex-col bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900"
  >
    <!-- Header -->
    <header class="absolute top-0 left-0 right-0 h-14 px-6 flex items-center justify-between z-10">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-sm">MG</span>
        </div>
        <span class="text-white/80 font-medium">MindGraph Pro</span>
      </div>

      <div class="flex items-center gap-2">
        <!-- Theme Toggle -->
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

        <!-- Language Toggle -->
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
        <!-- Background decorations -->
        <div class="absolute -top-20 -right-20 w-40 h-40 bg-primary-500/20 rounded-full blur-3xl" />
        <div
          class="absolute -bottom-20 -left-20 w-40 h-40 bg-indigo-500/20 rounded-full blur-3xl"
        />

        <!-- Card Content -->
        <div
          class="relative bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl p-8 shadow-2xl"
        >
          <slot />
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="py-4 text-center text-white/40 text-sm">
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

/* Override Element Plus styles for auth page */
:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: none;
}

:deep(.el-input__wrapper:hover) {
  border-color: rgba(255, 255, 255, 0.4);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

:deep(.el-input__inner) {
  color: white;
}

:deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.5);
}

:deep(.el-form-item__label) {
  color: rgba(255, 255, 255, 0.8);
}
</style>
