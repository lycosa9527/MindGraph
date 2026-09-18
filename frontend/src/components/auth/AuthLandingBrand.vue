<script setup lang="ts">
/**
 * Full-bleed brand backdrop for `/auth` — photo hero + overlay copy.
 */
import authLandingHero from '@/assets/auth/auth-landing-hero.png'
import { useLanguage } from '@/composables'

const { t } = useLanguage()
</script>

<template>
  <section
    class="auth-landing-brand"
    aria-labelledby="auth-landing-brand-title"
  >
    <img
      :src="authLandingHero"
      alt=""
      class="auth-landing-brand__bg"
      width="2560"
      height="1440"
      decoding="async"
      fetchpriority="high"
    />
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
  color: rgb(41 37 36);
  background: #e8eef8;
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
  filter: contrast(1.06) saturate(1.04);
}

.auth-landing-brand__veil {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  /* Minimal wash only near the login card so the hero stays crisp. */
  background: linear-gradient(
    90deg,
    transparent 0%,
    transparent 55%,
    rgb(248 250 252 / 0.12) 78%,
    rgb(248 250 252 / 0.32) 100%
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
    /* Leave room for the login card on the same 1280px rail. */
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
  color: rgb(15 23 42);
}

.auth-landing-brand__accent {
  background: linear-gradient(90deg, #3b82f6 0%, #7c5cbf 100%);
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
  color: rgb(51 65 85);
}

@media (max-width: 899px) {
  .auth-landing-brand__bg {
    object-position: 18% center;
  }

  .auth-landing-brand__veil {
    background: linear-gradient(
      180deg,
      rgb(248 250 252 / 0.72) 0%,
      rgb(248 250 252 / 0.35) 38%,
      rgb(248 250 252 / 0.12) 100%
    );
  }

  .auth-landing-brand__content {
    gap: 1.1rem;
    padding: 1.5rem 1.25rem 40vh;
    text-align: left;
    justify-content: flex-start;
  }

  .auth-landing-brand__top {
    max-width: none;
  }

  .auth-landing-brand__headline {
    max-width: none;
    font-size: 1.45rem;
  }

  .auth-landing-brand__subcopy {
    font-size: 0.9rem;
  }
}
</style>
