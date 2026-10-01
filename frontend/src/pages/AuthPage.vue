<script setup lang="ts">
/**
 * Dedicated /auth route — full-bleed brand background + white login card.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { LocationQuery, RouteLocationNormalizedLoaded } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'

import {
  AuthContactConsultModal,
  AuthLandingBrand,
  AuthLegalFooter,
  AuthMarketingNav,
  AuthQuickRegisterModal,
  LoginModal,
} from '@/components/auth'
import { useAuthStore, useUIStore } from '@/stores'
import { getSafePostAuthPath } from '@/utils/authRedirect'
import { clearPersistedOAuthLoginError } from '@/utils/oauthLoginUi'
import {
  clearStoredQuickRegToken,
  extractQuickRegTokenFromRedirect,
  normalizeQuickRegToken,
  readStoredQuickRegToken,
  writeStoredQuickRegToken,
} from '@/utils/quickRegToken'
import '@/styles/authPageCard.css'

const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const authStore = useAuthStore()

const showLoginModal = ref(true)
const showContactModal = ref(false)
const dismissedBySuccess = ref(false)
const quickRegToken = ref('')
const loginModalRef = ref<{
  openRegister?: () => void
  openLogin?: () => void
} | null>(null)

function extractQuickRegFromRoute(
  r: RouteLocationNormalizedLoaded | { query: LocationQuery }
): string {
  const top = r.query.quick_reg
  if (typeof top === 'string') {
    const fromTop = normalizeQuickRegToken(top)
    if (fromTop) {
      return fromTop
    }
  }
  const red = r.query.redirect
  if (typeof red !== 'string' || !red) {
    return ''
  }
  return extractQuickRegTokenFromRedirect(red, window.location.origin)
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

async function hydrateAuthModeAndResolveQuickReg(): Promise<void> {
  await authStore.detectMode()

  let t0 = extractQuickRegFromRoute(route) || readStoredQuickRegToken()
  if (t0 && !authStore.registrationEnabled) {
    const hadQuickInQuery =
      Boolean(route.query.quick_reg) ||
      (typeof route.query.redirect === 'string' && route.query.redirect.includes('quick_reg'))
    if (hadQuickInQuery) {
      void router.replace({ path: route.path, query: buildSanitizedQuery(route) })
    }
    clearStoredQuickRegToken()
    t0 = ''
  }
  if (t0) {
    quickRegToken.value = t0
    writeStoredQuickRegToken(t0)
    if (route.query.quick_reg) {
      void router.replace({ path: route.path, query: buildSanitizedQuery(route) })
    }
  }
}

onMounted(() => {
  document.documentElement.classList.remove('dark')
  void hydrateAuthModeAndResolveQuickReg()
})

watch(
  () => route.query,
  () => {
    if (quickRegToken.value) {
      return
    }
    void hydrateAuthModeAndResolveQuickReg()
  },
  { deep: true }
)

function onLoginSuccess() {
  clearPersistedOAuthLoginError()
  dismissedBySuccess.value = true
  const isStudent = authStore.user?.role === 'student'
  const fallback = isStudent ? '/learning-space' : '/mindmate'
  const redir = getSafePostAuthPath(route.query.redirect, fallback)
  const target =
    isStudent &&
    (redir === '/mindmate' || redir === '/' || redir === '/m' || redir === '/m/mindmate')
      ? '/learning-space'
      : redir
  router.push(target).catch(() => {
    void router.replace(target).catch(() => {
      window.location.href = target
    })
  })
}

function onQuickRegSuccess() {
  dismissedBySuccess.value = true
  showLoginModal.value = false
  clearStoredQuickRegToken()
  onLoginSuccess()
}

function onQuickRegCancel() {
  clearStoredQuickRegToken()
  quickRegToken.value = ''
  showLoginModal.value = true
  void router.replace({ path: '/auth' })
}

function onNavLogin() {
  loginModalRef.value?.openLogin?.()
  document.querySelector('.auth-page-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function onNavContact() {
  showContactModal.value = true
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
  <div class="auth-page">
    <AuthMarketingNav
      @login="onNavLogin"
      @contact="onNavContact"
    />

    <AuthContactConsultModal v-model="showContactModal" />

    <div class="auth-page-stage">
      <AuthLandingBrand class="auth-page-stage__brand" />

      <div class="auth-page-stage__content">
        <section
          class="auth-page-card"
          data-tsec-anchor
        >
          <div class="auth-page-card__form">
            <AuthQuickRegisterModal
              v-if="useQuickRegPanel"
              :quick-reg-token="quickRegToken"
              auth-page
              light-backdrop
              persistent
              @success="onQuickRegSuccess"
              @cancel="onQuickRegCancel"
            />

            <LoginModal
              v-else
              ref="loginModalRef"
              v-model:visible="showLoginModal"
              auth-page
              light-backdrop
              persistent
              @success="onLoginSuccess"
              @contact="onNavContact"
            />
            <AuthLegalFooter />
          </div>
          <footer
            v-if="useQuickRegPanel"
            class="auth-page-card__legal"
          >
            <span>
              <I18nText k="auth.landing.legalPrefix" />
              <RouterLink
                to="/privacy"
                target="_blank"
                rel="noopener noreferrer"
                class="auth-page-card__legal-link"
              >
                <I18nText k="auth.softwareAgreementLink" />
              </RouterLink>
            </span>
          </footer>
        </section>
      </div>
    </div>

    <p class="auth-page-icp">
      <I18nText k="auth.landing.copyright" />
    </p>
  </div>
</template>

<style scoped>
.auth-page {
  position: relative;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: #f3eefc;
}

.auth-page-icp {
  position: absolute;
  left: 50%;
  bottom: max(0.75rem, env(safe-area-inset-bottom, 0px));
  z-index: 2;
  margin: 0;
  transform: translateX(-50%);
  font-size: 0.75rem;
  line-height: 1.2;
  color: rgb(100 116 139);
  text-align: center;
  pointer-events: none;
  white-space: nowrap;
}

.auth-page-stage {
  position: relative;
  flex: 1;
  min-height: calc(100dvh - 3.75rem);
  overflow: hidden;
}

.auth-page-stage__brand {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.auth-page-stage__content {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  box-sizing: border-box;
  width: 100%;
  max-width: 1280px;
  min-height: calc(100dvh - 3.75rem);
  margin: 0 auto;
  padding: clamp(1.25rem, 3vw, 2rem) 1.25rem;
  pointer-events: none;
}

@media (max-width: 899px) {
  .auth-page-stage__content {
    justify-content: center;
    align-items: flex-start;
    padding-top: 4.75rem;
  }
}
</style>
