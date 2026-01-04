<script setup lang="ts">
/**
 * Not Found Page - 404 error page
 */
import { useRouter } from 'vue-router'

import { useLanguage } from '@/composables'

const router = useRouter()
// t reserved for future i18n
const { t: _t } = useLanguage()

function goHome() {
  router.push('/')
}

function goBack() {
  router.back()
}
</script>

<template>
  <div
    class="not-found-page flex flex-col items-center justify-center min-h-[60vh] text-center p-6"
  >
    <!-- 404 Illustration -->
    <div class="mb-8">
      <div class="text-9xl font-bold text-gray-200 dark:text-gray-700">404</div>
    </div>

    <!-- Message -->
    <h1 class="text-2xl font-bold text-gray-800 dark:text-white mb-3">Page Not Found</h1>
    <p class="text-gray-500 dark:text-gray-400 mb-8 max-w-md">
      The page you're looking for doesn't exist or has been moved.
    </p>

    <!-- Actions -->
    <div class="flex gap-4">
      <el-button @click="goBack">
        <el-icon class="mr-1"><ArrowLeft /></el-icon>
        Go Back
      </el-button>
      <el-button
        type="primary"
        @click="goHome"
      >
        <el-icon class="mr-1"><HomeFilled /></el-icon>
        Home
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.not-found-page {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
