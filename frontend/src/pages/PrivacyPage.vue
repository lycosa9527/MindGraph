<script setup lang="ts">
/**
 * Public Terms + Privacy page (same content as /auth modal, plus browser extension appendix).
 * Language: browser default with manual zh/en segmented control.
 */
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import SoftwareAgreementDocument from '@/components/auth/SoftwareAgreementDocument.vue'
import {
  PRIVACY_PAGE_LANGUAGE_OPTIONS,
  usePrivacyPageLocale,
} from '@/composables/usePrivacyPageLocale'

const { privacyPageUiCode, chrome, agreement, extensionSections, updatedLabel, syncFromBrowser } =
  usePrivacyPageLocale()

onMounted(() => {
  syncFromBrowser()
})
</script>

<template>
  <div class="privacy-page min-h-screen h-full overflow-y-auto bg-stone-50 text-stone-800">
    <header class="privacy-page__header">
      <div class="privacy-page__header-inner">
        <RouterLink
          to="/auth"
          class="privacy-page__brand"
        >
          MindGraph
        </RouterLink>
        <RouterLink
          to="/auth"
          class="privacy-page__back"
        >
          {{ chrome.backToSignIn }}
        </RouterLink>
      </div>
    </header>

    <main class="privacy-page__main">
      <article class="privacy-page__article">
        <header class="privacy-page__title-block">
          <div class="privacy-page__title-row">
            <h1 class="privacy-page__title">
              {{ agreement.title }}
            </h1>
            <AdminSwissSegmented
              v-model="privacyPageUiCode"
              :options="PRIVACY_PAGE_LANGUAGE_OPTIONS"
              aria-label="Language / 语言"
              equal
            />
          </div>
          <p class="privacy-page__updated">
            {{ updatedLabel }}
          </p>
        </header>

        <SoftwareAgreementDocument
          :agreement="agreement"
          :extra-sections="extensionSections"
        />
      </article>
    </main>

    <footer class="privacy-page__footer">
      <p>京ICP备2025126228号</p>
    </footer>
  </div>
</template>

<style scoped>
.privacy-page__header {
  border-bottom: 1px solid rgb(231 229 228);
  background: rgb(255 255 255);
}

.privacy-page__header-inner {
  max-width: 48rem;
  margin: 0 auto;
  padding: 0.85rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.privacy-page__brand {
  font-weight: 600;
  color: rgb(28 25 23);
  text-decoration: none;
}

.privacy-page__brand:hover {
  color: rgb(120 53 15);
}

.privacy-page__back {
  font-size: 0.875rem;
  color: rgb(120 113 108);
  text-decoration: none;
}

.privacy-page__back:hover {
  color: rgb(28 25 23);
  text-decoration: underline;
}

.privacy-page__main {
  max-width: 48rem;
  margin: 0 auto;
  padding: 2rem 1.25rem 3rem;
}

.privacy-page__article {
  background: rgb(255 255 255);
  border: 1px solid rgb(231 229 228);
  border-radius: 1rem;
  padding: 1.75rem 1.5rem 2rem;
  box-shadow: 0 1px 3px rgba(28, 25, 23, 0.06);
}

.privacy-page__title-block {
  margin-bottom: 0;
}

.privacy-page__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.privacy-page__title {
  margin: 0;
  flex: 1 1 12rem;
  min-width: 0;
  font-size: 1.35rem;
  font-weight: 600;
  line-height: 1.35;
  color: rgb(28 25 23);
}

.privacy-page__updated {
  margin: 0.5rem 0 1.5rem;
  font-size: 0.8125rem;
  color: rgb(120 113 108);
}

.privacy-page__footer {
  padding: 1.5rem 1.25rem 2rem;
  text-align: center;
  font-size: 0.75rem;
  color: rgb(168 162 158);
}
</style>
