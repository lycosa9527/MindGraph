<script setup lang="ts">
/**
 * Dashboard Login Page - Login for public dashboard access
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useNotifications } from '@/composables'

const router = useRouter()
const notify = useNotifications()

const accessCode = ref('')
const isLoading = ref(false)

async function handleLogin() {
  if (!accessCode.value.trim()) {
    notify.warning('Please enter an access code')
    return
  }

  isLoading.value = true

  try {
    // TODO: Validate access code with API
    // For now, any code works
    notify.success('Access granted')
    router.push('/dashboard')
  } catch {
    notify.error('Invalid access code')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="dashboard-login-page">
    <!-- Logo -->
    <div class="text-center mb-8">
      <div
        class="w-16 h-16 bg-gradient-to-br from-teal-500 to-cyan-600 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-lg"
      >
        <el-icon
          :size="32"
          class="text-white"
          ><DataAnalysis
        /></el-icon>
      </div>
      <h1 class="text-2xl font-bold text-white mb-2">Dashboard Access</h1>
      <p class="text-white/60">Enter your access code to view statistics</p>
    </div>

    <!-- Login Form -->
    <el-form @submit.prevent="handleLogin">
      <el-form-item>
        <el-input
          v-model="accessCode"
          size="large"
          placeholder="Access code"
          prefix-icon="Key"
          autocomplete="off"
        />
      </el-form-item>

      <el-form-item class="mt-6">
        <el-button
          type="primary"
          size="large"
          :loading="isLoading"
          class="w-full"
          native-type="submit"
        >
          View Dashboard
        </el-button>
      </el-form-item>
    </el-form>

    <!-- Public Access Link -->
    <div class="text-center mt-6">
      <el-button
        link
        class="!text-white/60 hover:!text-white"
        @click="router.push('/dashboard')"
      >
        View Public Dashboard
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.dashboard-login-page {
  width: 100%;
}
</style>
