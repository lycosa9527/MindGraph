<script setup lang="ts">
/**
 * Demo Login Page - Simplified demo access
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()
const { isZh } = useLanguage()
const notify = useNotifications()

const demoCode = ref('')
const isLoading = ref(false)

async function handleDemoLogin() {
  if (!demoCode.value.trim()) {
    notify.warning(isZh.value ? '请输入演示码' : 'Please enter a demo code')
    return
  }

  isLoading.value = true

  try {
    // Demo login uses code as password
    const result = await authStore.login({ username: 'demo', password: demoCode.value })
    const success = result.success

    if (success) {
      const userName = result.user?.username || ''
      notify.success(
        isZh.value
          ? userName
            ? `${userName}，登录成功`
            : '登录成功'
          : userName
            ? `Welcome, ${userName}`
            : 'Login successful'
      )
      router.push('/')
    } else {
      notify.error(result.message || (isZh.value ? '演示码无效' : 'Invalid demo code'))
    }
  } catch (error) {
    console.error('Demo login error:', error)
    notify.error(isZh.value ? '网络错误，登录失败' : 'Network error, login failed')
  } finally {
    isLoading.value = false
  }
}

function goToLogin() {
  router.push('/login')
}
</script>

<template>
  <div class="demo-login-page">
    <!-- Logo -->
    <div class="text-center mb-8">
      <div
        class="w-16 h-16 bg-linear-to-br from-indigo-500 to-purple-600 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-lg"
      >
        <span class="text-white font-bold text-2xl">MG</span>
      </div>
      <h1 class="text-2xl font-bold text-white mb-2">Demo Access</h1>
      <p class="text-white/60">Enter your demo code to get started</p>
    </div>

    <!-- Demo Form -->
    <el-form @submit.prevent="handleDemoLogin">
      <el-form-item>
        <el-input
          v-model="demoCode"
          size="large"
          placeholder="Enter demo code"
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
          Start Demo
        </el-button>
      </el-form-item>
    </el-form>

    <!-- Back to Login -->
    <div class="text-center mt-6">
      <el-button
        link
        class="text-white/60! hover:text-white!"
        @click="goToLogin"
      >
        Back to Login
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.demo-login-page {
  width: 100%;
}
</style>
