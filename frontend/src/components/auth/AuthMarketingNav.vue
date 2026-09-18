<script setup lang="ts">
/**
 * Top marketing nav for `/auth` (mock: logo + links + login/register CTAs).
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

const emit = defineEmits<{
  login: []
  register: []
  contact: []
}>()

const { t } = useLanguage()
const router = useRouter()
const authStore = useAuthStore()

/** Same KDocs doc as sidebar account menu 「快速指南」. */
const PLATFORM_QUICK_GUIDE_URL = 'https://365.kdocs.cn/l/caSETdpB0Akg'

const showRegisterCta = computed(() => authStore.registrationEnabled)

const navLinks = computed(() => [
  { key: 'contact', label: t('auth.landing.navContact') },
])

function go(to: string) {
  void router.push(to).catch(() => undefined)
}

function openPlatformQuickGuide(): void {
  window.open(PLATFORM_QUICK_GUIDE_URL, '_blank', 'noopener,noreferrer')
}

function onNavLink(link: { key: string }) {
  if (link.key === 'contact') {
    emit('contact')
  }
}
</script>

<template>
  <header class="auth-mkt-nav">
    <div class="auth-mkt-nav__inner">
      <div class="auth-mkt-nav__left">
        <button
          type="button"
          class="auth-mkt-nav__brand"
          @click="go('/auth')"
        >
          <span
            class="auth-mkt-nav__logo"
            aria-hidden="true"
          >M</span>
          <span class="auth-mkt-nav__brand-text">
            <span class="auth-mkt-nav__name">{{ t('app.brandName') }}</span>
            <span class="auth-mkt-nav__tagline">{{ t('auth.modal.tagline') }}</span>
          </span>
        </button>
        <nav
          class="auth-mkt-nav__links"
          :aria-label="t('auth.landing.navAria')"
        >
          <button
            v-for="link in navLinks"
            :key="link.key"
            type="button"
            class="auth-mkt-nav__link"
            @click="onNavLink(link)"
          >
            {{ link.label }}
          </button>
        </nav>
      </div>

      <div class="auth-mkt-nav__right">
        <button
          type="button"
          class="auth-mkt-nav__link auth-mkt-nav__link--muted"
          @click="openPlatformQuickGuide"
        >
          {{ t('auth.platformQuickGuide') }}
        </button>
        <button
          type="button"
          class="auth-mkt-nav__link"
          @click="emit('login')"
        >
          {{ t('auth.login') }}
        </button>
        <button
          v-if="showRegisterCta"
          type="button"
          class="auth-mkt-nav__register"
          @click="emit('register')"
        >
          {{ t('auth.landing.navRegisterFree') }}
        </button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.auth-mkt-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  height: 3.75rem;
  background: #fff;
  border-bottom: 1px solid rgb(237 233 254);
}

.auth-mkt-nav__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  height: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 1.25rem;
}

.auth-mkt-nav__left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  min-width: 0;
}

.auth-mkt-nav__brand {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  flex-shrink: 0;
}

.auth-mkt-nav__logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.5rem;
  background: #1c1917;
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.02em;
  flex-shrink: 0;
}

.auth-mkt-nav__brand-text {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.05rem;
  line-height: 1.15;
  text-align: left;
}

.auth-mkt-nav__name {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: rgb(28 25 23);
}

.auth-mkt-nav__tagline {
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: rgb(148 163 184);
  white-space: nowrap;
}

.auth-mkt-nav__links {
  display: flex;
  align-items: center;
  gap: 0.15rem;
}

.auth-mkt-nav__link {
  margin: 0;
  padding: 0.4rem 0.7rem;
  border: 0;
  border-radius: 0.5rem;
  background: transparent;
  font-size: 0.875rem;
  font-weight: 500;
  color: rgb(68 64 60);
  cursor: pointer;
  white-space: nowrap;
}

.auth-mkt-nav__link:hover {
  color: rgb(79 70 229);
  background: rgb(245 243 255);
}

.auth-mkt-nav__link--muted {
  color: rgb(120 113 108);
}

.auth-mkt-nav__right {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.auth-mkt-nav__register {
  margin-left: 0.35rem;
  padding: 0.45rem 0.95rem;
  border: 0;
  border-radius: 999px;
  background: rgb(237 233 254);
  color: rgb(79 70 229);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.auth-mkt-nav__register:hover {
  background: rgb(221 214 254);
}
</style>
