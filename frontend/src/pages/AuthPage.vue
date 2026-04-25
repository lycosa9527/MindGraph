<script setup lang="ts">
/**
 * Dedicated /auth route — full login/register or quick registration when `quick_reg` is present.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { LocationQuery, RouteLocationNormalizedLoaded } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'

import { AuthQuickRegisterModal, LoginModal } from '@/components/auth'
import { useLanguage } from '@/composables'
import { useUIStore } from '@/stores'
import { getSafePostAuthPath } from '@/utils/authRedirect'

const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const { t } = useLanguage()

const showLoginModal = ref(true)
const dismissedBySuccess = ref(false)
const quickRegToken = ref('')

/**
 * Opaque quick-reg token from `?quick_reg=` or from `?redirect=` query string.
 */
function extractQuickRegFromRoute(
  r: RouteLocationNormalizedLoaded | { query: LocationQuery }
): string {
  const top = r.query.quick_reg
  if (typeof top === 'string' && top.trim()) {
    return top.trim()
  }
  const red = r.query.redirect
  if (typeof red !== 'string' || !red) {
    return ''
  }
  try {
    const pathForUrl = red.startsWith('http')
      ? red
      : `${window.location.origin}${red.startsWith('/') ? '' : '/'}${red}`
    const u = new URL(pathForUrl)
    const t = u.searchParams.get('quick_reg')
    return t && t.trim() ? t.trim() : ''
  } catch {
    return ''
  }
}

function buildSanitizedQuery(r: RouteLocationNormalizedLoaded) {
  const next: Record<string, string> = {}
  for (const [k, v] of Object.entries(r.query)) {
    if (k === 'quick_reg' || v === undefined) {
      continue
    }
    if (k === 'redirect' && typeof v === 'string' && v.includes('quick_reg')) {
      try {
        const pathForUrl = v.startsWith('http')
          ? v
          : `${window.location.origin}${v.startsWith('/') ? '' : '/'}${v}`
        const u = new URL(pathForUrl)
        u.searchParams.delete('quick_reg')
        next[k] = `${u.pathname}${u.search}${u.hash}` || v
        continue
      } catch {
        next[k] = v
        continue
      }
    }
    if (Array.isArray(v)) {
      if (v[0] !== undefined) {
        next[k] = String(v[0])
      }
    } else {
      next[k] = String(v)
    }
  }
  return next
}

const useQuickRegPanel = computed(() => quickRegToken.value.length > 0)

onMounted(() => {
  document.documentElement.classList.remove('dark')
  uiStore.syncGuestLocaleFromBrowser()
  const t0 = extractQuickRegFromRoute(route)
  if (t0) {
    quickRegToken.value = t0
    if (route.query.quick_reg) {
      void router.replace({ path: route.path, query: buildSanitizedQuery(route) })
    }
  }
})

watch(
  () => route.query,
  () => {
    if (quickRegToken.value) {
      return
    }
    const t0 = extractQuickRegFromRoute(route)
    if (t0) {
      quickRegToken.value = t0
      if (route.query.quick_reg) {
        void router.replace({ path: route.path, query: buildSanitizedQuery(route) })
      }
    }
  },
  { deep: true }
)

function onLoginSuccess() {
  dismissedBySuccess.value = true
  const redir = getSafePostAuthPath(route.query.redirect)
  router
    .push(redir)
    .catch(() => {
      void router
        .replace(redir)
        .catch(() => {
          window.location.href = redir
        })
    })
}

function onQuickRegSuccess() {
  dismissedBySuccess.value = true
  showLoginModal.value = false
  // Keep `quickRegToken` until the route leaves `/auth` so the login modal does not
  // mount for a frame before navigation (avoids a flash of the standard sign-in).
  onLoginSuccess()
}

function onQuickRegCancel() {
  quickRegToken.value = ''
  showLoginModal.value = true
  void router.replace({ path: '/auth' })
}

watch(showLoginModal, (visible) => {
  if (quickRegToken.value) {
    return
  }
  if (!visible && !dismissedBySuccess.value) {
    void router.replace('/').catch(() => {
      window.location.href = '/'
    })
  }
})

onBeforeUnmount(() => {
  if (uiStore.isDark) {
    document.documentElement.classList.add('dark')
  }
})
</script>

<template>
  <div>
    <div
      v-if="!useQuickRegPanel"
      class="text-center py-6 px-2"
    >
      <p class="text-stone-400 text-sm tracking-widest uppercase">
        {{ t('auth.modal.tagline') }}
      </p>
    </div>

    <AuthQuickRegisterModal
      v-if="useQuickRegPanel"
      :quick-reg-token="quickRegToken"
      light-backdrop
      persistent
      @success="onQuickRegSuccess"
      @cancel="onQuickRegCancel"
    />

    <LoginModal
      v-else
      v-model:visible="showLoginModal"
      light-backdrop
      persistent
      @success="onLoginSuccess"
    />
  </div>
</template>
