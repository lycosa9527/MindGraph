<script setup lang="ts">
/**
 * Full-bleed cinematic hero for `/auth` — COS clip on test/prod, still in Vite.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import authLandingPoster from '@/assets/auth/auth-landing-hero.png'
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
const heroSrc = ref('')
const heroKind = ref<AuthLoginHeroKind>('image')
const videoFailed = ref(false)
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

function onVideoError(): void {
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
    <video
      v-if="showVideo"
      :key="heroSrc"
      class="auth-landing-brand__bg"
      :poster="authLandingPoster"
      autoplay
      muted
      loop
      playsinline
      preload="auto"
      @error="onVideoError"
    >
      <source
        :src="heroSrc"
        type="video/mp4"
      >
    </video>
    <img
      v-else
      :src="heroSrc || authLandingPoster"
      alt=""
      class="auth-landing-brand__bg"
      width="2048"
      height="1152"
      decoding="async"
      fetchpriority="high"
    >

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
  color: rgb(248 250 252);
  background: #0b1220;
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

.auth-landing-brand__veil {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    rgb(8 15 30 / 0.22) 0%,
    transparent 40%,
    rgb(248 250 252 / 0.10) 78%,
    rgb(248 250 252 / 0.28) 100%
  );
}

.auth-landing-brand__content {
  position: relative;
  z-index: 2;
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
  color: #fff;
  text-shadow: 0 2px 18px rgb(8 15 30 / 0.45);
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
  color: rgb(226 232 240);
  text-shadow: 0 1px 10px rgb(8 15 30 / 0.35);
}

@media (max-width: 899px) {
  .auth-landing-brand__bg {
    object-position: 18% center;
  }

  .auth-landing-brand__veil {
    background: linear-gradient(
      180deg,
      rgb(8 15 30 / 0.72) 0%,
      rgb(8 15 30 / 0.35) 38%,
      rgb(8 15 30 / 0.12) 100%
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
