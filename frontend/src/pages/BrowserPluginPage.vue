<script setup lang="ts">
/**
 * Public intro for the Chrome / Edge extension.
 * Same zip serves both browsers.
 */
import { useRouter } from 'vue-router'

import { ArrowLeft, FileDown, MessageCircle, Network } from '@lucide/vue'

import documentShot from '@/assets/browser-plugin/document.png'
import mapShot from '@/assets/browser-plugin/mind-map.png'
import mindmateShot from '@/assets/browser-plugin/mindmate.png'
import BrowserPluginMark from '@/components/common/BrowserPluginMark.vue'
import I18nText from '@/components/common/I18nText.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import { useAuthStore } from '@/stores/auth'

const ZIP_URL = '/api/downloads/mindgraph-chrome-extension'

const router = useRouter()
const authStore = useAuthStore()
const notify = useNotifications()
const { t } = useLanguage()
const { canUseChromeExtension } = useSchoolTierFeatures()

const cards = [
  {
    key: 'map',
    icon: Network,
    title: 'browserPlugin.cardMapTitle',
    body: 'browserPlugin.cardMapBody',
    tone: 'peach',
  },
  {
    key: 'chat',
    icon: MessageCircle,
    title: 'browserPlugin.cardChatTitle',
    body: 'browserPlugin.cardChatBody',
    tone: 'lilac',
  },
  {
    key: 'doc',
    icon: FileDown,
    title: 'browserPlugin.cardDocTitle',
    body: 'browserPlugin.cardDocBody',
    tone: 'sky',
  },
] as const

const bands = [
  {
    key: 'map',
    title: 'browserPlugin.mapTitle',
    body: 'browserPlugin.mapBody',
    image: mapShot,
    alt: 'browserPlugin.cardMapTitle',
    flip: false,
  },
  {
    key: 'chat',
    title: 'browserPlugin.chatTitle',
    body: 'browserPlugin.chatBody',
    image: mindmateShot,
    alt: 'browserPlugin.cardChatTitle',
    flip: true,
  },
  {
    key: 'doc',
    title: 'browserPlugin.docTitle',
    body: 'browserPlugin.docBody',
    image: documentShot,
    alt: 'browserPlugin.cardDocTitle',
    flip: false,
  },
] as const

function goBack(): void {
  void router.push('/mindmate')
}

function downloadPlugin(): void {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  if (!canUseChromeExtension.value) {
    notify.errorKey('auth.schoolTierFeatureUnavailable')
    return
  }
  const link = document.createElement('a')
  link.href = ZIP_URL
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}
</script>

<template>
  <div class="plugin-page">
    <header class="plugin-top">
      <button
        type="button"
        class="plugin-back"
        @click="goBack"
      >
        <ArrowLeft
          :size="16"
          :stroke-width="2"
        />
        <I18nText
          k="browserPlugin.back"
          dense
          primary-only
        />
      </button>
      <span class="plugin-brand">
        <I18nText
          k="app.brandName"
          dense
          primary-only
        />
      </span>
    </header>

    <section class="plugin-hero">
      <div class="plugin-hero__copy">
        <h1>
          <span class="plugin-hero__mark">
            <I18nText
              k="browserPlugin.heroMark"
              dense
              primary-only
            />
          </span>
          <I18nText
            k="browserPlugin.heroTitle"
            dense
            primary-only
          />
        </h1>
        <p>
          <I18nText k="browserPlugin.heroBody" />
        </p>
        <div class="plugin-pills">
          <button
            type="button"
            class="plugin-pill"
            @click="downloadPlugin"
          >
            <span
              class="plugin-pill__mark"
              aria-hidden="true"
            >
              <BrowserPluginMark browser="chrome" />
            </span>
            <I18nText
              k="browserPlugin.downloadChrome"
              dense
              primary-only
            />
          </button>
          <button
            type="button"
            class="plugin-pill"
            @click="downloadPlugin"
          >
            <span
              class="plugin-pill__mark"
              aria-hidden="true"
            >
              <BrowserPluginMark browser="edge" />
            </span>
            <I18nText
              k="browserPlugin.downloadEdge"
              dense
              primary-only
            />
          </button>
        </div>
      </div>
      <div class="plugin-hero__stage">
        <svg
          class="plugin-illu"
          viewBox="0 0 640 420"
          role="img"
          :aria-label="t('browserPlugin.heroTitle')"
        >
          <ellipse
            cx="470"
            cy="86"
            rx="150"
            ry="72"
            fill="#ede9fe"
          />
          <ellipse
            cx="168"
            cy="340"
            rx="120"
            ry="48"
            fill="#dbeafe"
          />
          <rect
            x="36"
            y="78"
            width="390"
            height="268"
            rx="22"
            fill="#ffffff"
            stroke="#e7edf5"
            stroke-width="2"
          />
          <rect
            x="36"
            y="78"
            width="390"
            height="46"
            rx="22"
            fill="#f8fafc"
          />
          <rect
            x="36"
            y="102"
            width="390"
            height="22"
            fill="#f8fafc"
          />
          <circle
            cx="62"
            cy="100"
            r="6"
            fill="#fecaca"
          />
          <circle
            cx="82"
            cy="100"
            r="6"
            fill="#fde68a"
          />
          <circle
            cx="102"
            cy="100"
            r="6"
            fill="#bbf7d0"
          />
          <rect
            x="128"
            y="90"
            width="210"
            height="20"
            rx="10"
            fill="#ffffff"
          />
          <rect
            x="62"
            y="150"
            width="150"
            height="12"
            rx="6"
            fill="#e2e8f0"
          />
          <rect
            x="62"
            y="174"
            width="190"
            height="10"
            rx="5"
            fill="#f1f5f9"
          />
          <rect
            x="62"
            y="194"
            width="168"
            height="10"
            rx="5"
            fill="#f1f5f9"
          />
          <rect
            x="62"
            y="214"
            width="128"
            height="10"
            rx="5"
            fill="#f1f5f9"
          />
          <circle
            cx="250"
            cy="250"
            r="16"
            fill="#ddd6fe"
          />
          <circle
            cx="304"
            cy="214"
            r="12"
            fill="#bfdbfe"
          />
          <circle
            cx="312"
            cy="276"
            r="12"
            fill="#fde68a"
          />
          <path
            d="M262 242 L294 220 M260 258 L302 270"
            stroke="#c4b5fd"
            stroke-width="3"
            fill="none"
            stroke-linecap="round"
          />
          <rect
            x="292"
            y="46"
            width="286"
            height="320"
            rx="26"
            fill="#ffffff"
            stroke="#e7edf5"
            stroke-width="2"
          />
          <rect
            x="292"
            y="46"
            width="286"
            height="10"
            rx="5"
            fill="#7c3aed"
          />
          <rect
            x="316"
            y="78"
            width="44"
            height="44"
            rx="14"
            fill="#f3e8ff"
          />
          <path
            d="M332 92 h10 a6 6 0 0 1 6 6 v4 h4 a6 6 0 0 1 6 6 v10 h-10 a6 6 0 0 1-6-6 v-4 h-4 a6 6 0 0 1-6-6 z"
            fill="#7c3aed"
          />
          <rect
            x="372"
            y="84"
            width="92"
            height="12"
            rx="6"
            fill="#1e293b"
          />
          <rect
            x="372"
            y="104"
            width="140"
            height="8"
            rx="4"
            fill="#e2e8f0"
          />
          <g transform="translate(316 142)">
            <rect
              width="238"
              height="52"
              rx="14"
              fill="#f8fafc"
            />
            <path
              d="M78 18 H108 M78 34 H108 M152 26 H178"
              stroke="#c4b5fd"
              stroke-width="2"
              fill="none"
              stroke-linecap="round"
            />
            <rect
              x="34"
              y="12"
              width="44"
              height="12"
              rx="6"
              fill="#ddd6fe"
            />
            <rect
              x="34"
              y="28"
              width="44"
              height="12"
              rx="6"
              fill="#c4b5fd"
            />
            <rect
              x="108"
              y="18"
              width="44"
              height="16"
              rx="8"
              fill="#6d5efc"
            />
            <rect
              x="178"
              y="20"
              width="40"
              height="12"
              rx="6"
              fill="#ede9fe"
            />
          </g>
          <g transform="translate(316 206)">
            <rect
              width="238"
              height="52"
              rx="14"
              fill="#f8fafc"
            />
            <path
              d="M78 18 H108 M78 34 H108 M152 26 H178"
              stroke="#93c5fd"
              stroke-width="2"
              fill="none"
              stroke-linecap="round"
            />
            <rect
              x="34"
              y="12"
              width="44"
              height="12"
              rx="6"
              fill="#dbeafe"
            />
            <rect
              x="34"
              y="28"
              width="44"
              height="12"
              rx="6"
              fill="#bfdbfe"
            />
            <rect
              x="108"
              y="18"
              width="44"
              height="16"
              rx="8"
              fill="#2563eb"
            />
            <rect
              x="178"
              y="20"
              width="40"
              height="12"
              rx="6"
              fill="#e0f2fe"
            />
          </g>
          <rect
            x="348"
            y="286"
            width="174"
            height="44"
            rx="14"
            fill="#7c3aed"
          />
          <rect
            x="392"
            y="304"
            width="86"
            height="8"
            rx="4"
            fill="#ffffff"
          />
        </svg>
      </div>
    </section>

    <section class="plugin-entry">
      <h2>
        <I18nText
          k="browserPlugin.entryTitle"
          align="center"
        />
      </h2>
      <p>
        <I18nText
          k="browserPlugin.entryBody"
          align="center"
        />
      </p>
      <div class="plugin-cards">
        <article
          v-for="card in cards"
          :key="card.key"
          class="plugin-card"
          :class="`plugin-card--${card.tone}`"
        >
          <span class="plugin-card__icon">
            <component
              :is="card.icon"
              :size="22"
              :stroke-width="1.75"
            />
          </span>
          <h3>
            <I18nText :k="card.title" />
          </h3>
          <p>
            <I18nText :k="card.body" />
          </p>
        </article>
      </div>
    </section>

    <section
      v-for="band in bands"
      :key="band.key"
      class="plugin-band"
      :class="{ 'plugin-band--flip': band.flip }"
    >
      <img
        class="plugin-shot plugin-shot--band"
        :src="band.image"
        :alt="t(band.alt)"
      />
      <div class="plugin-band__copy">
        <h2>
          <I18nText :k="band.title" />
        </h2>
        <p>
          <I18nText :k="band.body" />
        </p>
      </div>
    </section>

    <section class="plugin-download">
      <h2>
        <I18nText
          k="browserPlugin.downloadTitle"
          align="center"
        />
      </h2>
      <p>
        <I18nText
          k="browserPlugin.downloadLead"
          align="center"
        />
      </p>
      <div class="plugin-download__cards">
        <button
          type="button"
          class="plugin-dl"
          @click="downloadPlugin"
        >
          <span
            class="plugin-dl__mark"
            aria-hidden="true"
          >
            <BrowserPluginMark browser="chrome" />
          </span>
          <span class="plugin-dl__name">
            <I18nText
              k="browserPlugin.downloadChrome"
              dense
              primary-only
            />
          </span>
          <span class="plugin-dl__action">
            <I18nText
              k="browserPlugin.downloadAction"
              dense
              primary-only
            />
          </span>
        </button>
        <button
          type="button"
          class="plugin-dl"
          @click="downloadPlugin"
        >
          <span
            class="plugin-dl__mark"
            aria-hidden="true"
          >
            <BrowserPluginMark browser="edge" />
          </span>
          <span class="plugin-dl__name">
            <I18nText
              k="browserPlugin.downloadEdge"
              dense
              primary-only
            />
          </span>
          <span class="plugin-dl__action">
            <I18nText
              k="browserPlugin.downloadAction"
              dense
              primary-only
            />
          </span>
        </button>
      </div>
      <p class="plugin-download__hint">
        <I18nText
          k="browserPlugin.installHint"
          align="center"
        />
      </p>
    </section>
  </div>
</template>

<style scoped>
.plugin-page {
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  background:
    radial-gradient(ellipse 70% 42% at 78% 8%, rgba(186, 220, 255, 0.55), transparent 68%),
    radial-gradient(ellipse 46% 32% at 12% 18%, rgba(224, 236, 255, 0.9), transparent 70%),
    linear-gradient(180deg, #f5f8ff 0%, #ffffff 28%, #ffffff 72%, #f3f7ff 100%);
  color: #1f2937;
}

.plugin-top,
.plugin-hero,
.plugin-entry,
.plugin-band,
.plugin-download {
  box-sizing: border-box;
  width: min(1080px, calc(100% - 48px));
  margin-inline: auto;
}

.plugin-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 0 8px;
}

.plugin-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  cursor: pointer;
}

.plugin-back:hover {
  color: #1e293b;
}

.plugin-brand {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #0f172a;
}

.plugin-hero {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
  gap: 36px;
  align-items: center;
  padding: 28px 0 56px;
}

.plugin-hero h1 {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: 0.2em;
  margin: 0;
  color: #2f6bff;
  font-size: clamp(36px, 4vw, 52px);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.15;
}

.plugin-hero__mark {
  color: #7c3aed;
}

.plugin-hero__copy > p,
.plugin-entry > p,
.plugin-download > p {
  margin: 14px 0 0;
  color: #64748b;
  font-size: 16px;
  line-height: 1.7;
}

.plugin-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 28px;
}

.plugin-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 48px;
  padding: 0 18px;
  border: 0;
  border-radius: 12px;
  background: #1f2937;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.plugin-pill:hover {
  background: #111827;
}

.plugin-pill__mark,
.plugin-dl__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.plugin-pill__mark :deep(svg),
.plugin-dl__mark :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
}

.plugin-hero__stage {
  display: flex;
  justify-content: center;
}

.plugin-illu {
  width: min(100%, 560px);
  height: auto;
  filter: drop-shadow(0 24px 40px rgba(124, 58, 237, 0.12));
}

.plugin-shot {
  width: min(100%, 560px);
  border-radius: 28px;
  background: #fff;
  box-shadow:
    0 30px 70px rgba(47, 107, 255, 0.12),
    0 8px 24px rgba(15, 23, 42, 0.06);
}

.plugin-entry {
  padding: 12px 0 28px;
  text-align: center;
}

.plugin-entry h2,
.plugin-download h2,
.plugin-band__copy h2 {
  margin: 0;
  color: #111827;
  font-size: clamp(26px, 3vw, 34px);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.25;
}

.plugin-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 28px;
  padding: 22px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.05);
  text-align: start;
}

.plugin-card {
  padding: 22px 18px 20px;
  border-radius: 22px;
}

.plugin-card--peach {
  background: #fff6ee;
}

.plugin-card--lilac {
  background: #f4f1ff;
}

.plugin-card--sky {
  background: #eef6ff;
}

.plugin-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: #fff;
  color: #334155;
}

.plugin-card h3 {
  margin: 14px 0 0;
  font-size: 17px;
  font-weight: 600;
  color: #111827;
}

.plugin-card p,
.plugin-band__copy p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
  line-height: 1.65;
}

.plugin-band {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 36px;
  align-items: center;
  padding: 36px 0;
}

.plugin-band--flip {
  grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
}

.plugin-band--flip .plugin-shot--band {
  order: 2;
}

.plugin-shot--band {
  width: 100%;
}

.plugin-download {
  padding: 48px 0 80px;
  text-align: center;
}

.plugin-download__cards {
  display: flex;
  justify-content: center;
  gap: 18px;
  margin-top: 28px;
}

.plugin-dl {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 180px;
  padding: 28px 16px 22px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 16px 40px rgba(47, 107, 255, 0.08);
  cursor: pointer;
}

.plugin-dl:hover {
  transform: translateY(-2px);
}

.plugin-dl__mark {
  width: 52px;
  height: 52px;
}

.plugin-dl__name {
  color: #111827;
  font-size: 16px;
  font-weight: 600;
}

.plugin-dl__action {
  color: #2f6bff;
  font-size: 14px;
}

.plugin-download__hint {
  max-width: 520px;
  margin: 22px auto 0;
  font-size: 13px;
}

@media (max-width: 860px) {
  .plugin-hero,
  .plugin-band,
  .plugin-band--flip,
  .plugin-cards {
    grid-template-columns: 1fr;
  }

  .plugin-band--flip .plugin-shot--band {
    order: 0;
  }

  .plugin-hero {
    padding-top: 12px;
  }
}
</style>
