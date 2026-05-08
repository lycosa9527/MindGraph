<script setup lang="ts">
/**
 * Bayi 6-digit passkey login (AUTH_MODE=bayi on server).
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useLanguage()
const notify = useNotifications()

const passkey = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  if (!passkey.value.trim()) {
    notify.warning(t('bayiPasskey.enterCode'))
    return
  }

  isLoading.value = true

  try {
    const result = await authStore.loginWithBayiPasskey(passkey.value.trim())
    if (result.success) {
      const userName = result.user?.username || ''
      notify.success(
        userName ? t('bayiPasskey.loginSuccessNamed', { name: userName }) : t('bayiPasskey.loginOk'),
      )
      router.push('/mindmate')
    } else {
      notify.error(result.message || t('bayiPasskey.invalidCode'))
    }
  } catch (error) {
    console.error('Bayi passkey login error:', error)
    notify.error(t('bayiPasskey.networkError'))
  } finally {
    isLoading.value = false
  }
}

function goToLogin() {
  router.push('/auth')
}
</script>

<template>
  <div class="bayi-passkey-page">
    <div class="text-center mb-8">
      <div
        class="w-16 h-16 bg-linear-to-br from-indigo-500 to-purple-600 rounded-2xl mx-auto mb-4 flex items-center justify-center shadow-lg"
      >
        <span class="text-white font-bold text-2xl">MG</span>
      </div>
      <h1 class="text-2xl font-bold text-white mb-2">{{ t('bayiPasskey.title') }}</h1>
      <p class="text-white/60">{{ t('bayiPasskey.subtitle') }}</p>
    </div>

    <el-form @submit.prevent="handleSubmit">
      <el-form-item>
        <el-input
          v-model="passkey"
          size="large"
          maxlength="6"
          :placeholder="t('bayiPasskey.enterCode')"
          prefix-icon="Key"
          autocomplete="one-time-code"
          inputmode="numeric"
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
          {{ t('bayiPasskey.submit') }}
        </el-button>
      </el-form-item>
    </el-form>

    <div class="text-center mt-6">
      <el-button
        link
        class="text-white/60! hover:text-white!"
        @click="goToLogin"
      >
        {{ t('bayiPasskey.back') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.bayi-passkey-page {
  width: 100%;
}
</style>
