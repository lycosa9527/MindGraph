<script setup lang="ts">
/**
 * Full-bleed cinematic hero for `/auth` — COS clip on test/prod, still in Vite.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { useLanguage } from '@/composables'
import {
  AUTH_LOGIN_HERO_NARROW_QUERY,
  AUTH_LOGIN_HERO_STILL_SRC,
  authLoginHeroKind,
  authLoginHeroShouldAnimate,
  authLoginHeroSrc,
  pickAuthLoginHeroId,
  type AuthLoginHeroKind,
} from '@/utils/authLoginHero'

const { t } = useLanguage()
const clipId = ref('')
const heroSrc = ref(AUTH_LOGIN_HERO_STILL_SRC)
const heroKind = ref<AuthLoginHeroKind>('image')
const videoFailed = ref(false)
const videoReady = ref(false)
const reduceMotion = ref(false)
const narrowViewport = ref(false)
const showVideo = computed(
  () =>
    heroKind.value === 'video' &&
    authLoginHeroShouldAnimate({
      reduceMotion: reduceMotion.value,
      narrowViewport: narrowViewport.value,
    }) &&
    !videoFailed.value &&
    Boolean(heroSrc.value)
)

let motionMq: MediaQueryList | null = null
let narrowMq: MediaQueryList | null = null

function applyHeroKind(): void {
  reduceMotion.value = Boolean(motionMq?.matches)
  narrowViewport.value = Boolean(narrowMq?.matches)
  const animate = authLoginHeroShouldAnimate({
    reduceMotion: reduceMotion.value,
    narrowViewport: narrowViewport.value,
  })
  const kind: AuthLoginHeroKind = animate ? authLoginHeroKind() : 'image'
  heroKind.value = kind
  if (!clipId.value) {
    clipId.value = pickAuthLoginHeroId()
  }
  heroSrc.value = authLoginHeroSrc(clipId.value, kind)
  videoReady.value = false
}

onMounted(() => {
  motionMq = window.matchMedia('(prefers-reduced-motion: reduce)')
  narrowMq = window.matchMedia(AUTH_LOGIN_HERO_NARROW_QUERY)
  motionMq.addEventListener('change', applyHeroKind)
  narrowMq.addEventListener('change', applyHeroKind)
  applyHeroKind()
})

onBeforeUnmount(() => {
  motionMq?.removeEventListener('change', applyHeroKind)
  narrowMq?.removeEventListener('change', applyHeroKind)
})

function onVideoReady(): void {
  videoReady.value = true
}

function onVideoError(): void {
  videoReady.value = false
  if (heroKind.value === 'video') {
    heroKind.value = 'image'
    heroSrc.value = AUTH_LOGIN_HERO_STILL_SRC
    return
  }
  videoFailed.value = true
}
</script>

<template>
  <section
    class="auth-landing-brand"
    aria-labelledby="auth-landing-brand-title"
  >
    <img
      :src="AUTH_LOGIN_HERO_STILL_SRC"
      alt=""
      class="auth-landing-brand__bg"
      width="1920"
      height="1080"
      decoding="async"
      fetchpriority="high"
    >
    <video
      v-if="showVideo"
      :key="heroSrc"
      class="auth-landing-brand__bg auth-landing-brand__video"
      :class="{ 'auth-landing-brand__video--ready': videoReady }"
      autoplay
      muted
      loop
      playsinline
      preload="auto"
      @canplay="onVideoReady"
      @error="onVideoError"
    >
      <source
        :src="heroSrc"
        type="video/mp4"
      >
    </video>

    <div
      class="auth-landing-brand__veil"
      aria-hidden="true"
    />

    <div class="auth-landing-brand__content">
      <div class="auth-landing-brand__top">
        <h1
          id="auth-landing-brand-title"
          class="auth-landing-brand__headline"
        >
          <span>{{ t('auth.landing.headlinePrefix') }}</span>
          <span class="auth-landing-brand__accent">{{ t('auth.landing.headlineAccent') }}</span>
        </h1>
        <p class="auth-landing-brand__subcopy">
          {{ t('auth.landing.subcopy') }}
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.auth-landing-brand {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  color: #2e1065;
  background: #f3eefc;
}

.auth-landing-brand__bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 18% center;
  image-rendering: auto;
  -webkit-backface-visibility: hidden;
  backface-visibility: hidden;
}

.auth-landing-brand__video {
  z-index: 1;
  opacity: 0;
}

.auth-landing-brand__video--ready {
  opacity: 1;
}

.auth-landing-brand__veil {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    rgb(243 238 252 / 0.28) 0%,
    transparent 42%,
    rgb(243 238 252 / 0.42) 78%,
    rgb(243 238 252 / 0.72) 100%
  );
}

.auth-landing-brand__content {
  position: relative;
  z-index: 3;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  box-sizing: border-box;
  width: 100%;
  max-width: 1280px;
  height: 100%;
  min-height: 0;
  margin: 0 auto;
  padding: clamp(1.75rem, 4vw, 2.5rem) 1.25rem clamp(1.25rem, 3vw, 2rem);
}

.auth-landing-brand__top {
  position: relative;
  box-sizing: border-box;
  width: fit-content;
  max-width: 100%;
  padding: 0.85rem 1.1rem 1rem;
}

.auth-landing-brand__top::before {
  content: '';
  position: absolute;
  z-index: -1;
  inset: 0;
  border-radius: 0.55rem;
  background: rgb(255 255 255 / 0.28);
  border: 1px solid rgb(255 255 255 / 0.42);
}

@media (min-width: 900px) {
  .auth-landing-brand__top {
    max-width: min(34rem, calc(100% - 26.5rem - 2rem));
  }
}

.auth-landing-brand__headline {
  margin: 0 0 0.9rem;
  max-width: 14em;
  font-size: clamp(1.85rem, 3.6vw, 2.75rem);
  font-weight: 800;
  letter-spacing: -0.035em;
  line-height: 1.2;
  color: #2e1065;
  text-shadow: none;
}

.auth-landing-brand__accent {
  background: linear-gradient(90deg, #7dd3fc 0%, #c4b5fd 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-weight: 800;
}

.auth-landing-brand__subcopy {
  margin: 0;
  max-width: 38em;
  font-size: 1rem;
  line-height: 1.7;
  color: #4c1d95;
  text-shadow: none;
}

@media (max-width: 899px) {
  .auth-landing-brand__bg {
    object-position: 18% center;
  }

  .auth-landing-brand__veil {
    background: linear-gradient(
      180deg,
      rgb(243 238 252 / 0.88) 0%,
      rgb(243 238 252 / 0.42) 38%,
      rgb(243 238 252 / 0.08) 100%
    );
  }

  .auth-landing-brand__content {
    gap: 0;
    padding: 1rem 1.25rem 0;
    text-align: left;
    justify-content: flex-start;
  }

  .auth-landing-brand__top {
    max-width: none;
    padding: 0.55rem 0.75rem 0.65rem;
  }

  .auth-landing-brand__headline {
    max-width: none;
    margin-bottom: 0;
    font-size: 1.2rem;
  }

  .auth-landing-brand__subcopy {
    display: none;
  }
}
</style>
