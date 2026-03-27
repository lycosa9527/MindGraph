<script setup lang="ts">
/**
 * Dedicated /auth route — reuses LoginModal (login, register, SMS, forgot password)
 * Single full-page auth entry (replaces legacy /login).
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { LoginModal } from '@/components/auth'
import { useLanguage } from '@/composables'
import { useUIStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const { t } = useLanguage()

const showLoginModal = ref(true)
const dismissedBySuccess = ref(false)

function onLoginSuccess() {
  dismissedBySuccess.value = true
  const redirect = (route.query.redirect as string) || '/'
  router.push(redirect).catch(() => {
    router.replace(redirect).catch(() => {
      window.location.href = redirect
    })
  })
}

watch(showLoginModal, (visible) => {
  if (!visible && !dismissedBySuccess.value) {
    router.replace('/').catch(() => {
      window.location.href = '/'
    })
  }
})

onMounted(() => {
  document.documentElement.classList.remove('dark')
  uiStore.syncGuestLocaleFromBrowser()
})

onBeforeUnmount(() => {
  if (uiStore.isDark) {
    document.documentElement.classList.add('dark')
  }
})
</script>

<template>
  <div class="text-center py-6 px-2">
    <p class="text-stone-400 text-sm tracking-widest uppercase">
      {{ t('auth.modal.tagline') }}
    </p>
  </div>

  <LoginModal
    v-model:visible="showLoginModal"
    light-backdrop
    @success="onLoginSuccess"
  />
</template>
