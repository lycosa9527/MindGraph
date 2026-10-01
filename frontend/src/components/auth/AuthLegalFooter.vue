<script setup lang="ts">
/**
 * Clickable Terms of Use + Privacy Policy links for /auth and session re-login.
 */
import { RouterLink } from 'vue-router'

import { useLanguage } from '@/composables'

const { t } = useLanguage()
</script>

<template>
  <p class="auth-legal-footer">
    <I18nText k="auth.landing.legalPrefix" />
    <RouterLink
      to="/privacy#user-agreement"
      target="_blank"
      rel="noopener noreferrer"
      class="auth-legal-footer__link"
    >
      <I18nText k="auth.landing.userAgreementLink" />
    </RouterLink>
    <I18nText k="auth.landing.legalJoin" />
    <RouterLink
      to="/privacy#privacy-policy"
      target="_blank"
      rel="noopener noreferrer"
      class="auth-legal-footer__link"
    >
      <I18nText k="auth.landing.privacyPolicyLink" />
    </RouterLink>
  </p>
</template>

<style scoped>
.auth-legal-footer {
  margin: 0;
  padding: 0.65rem 0 0.35rem;
  font-size: 0.75rem;
  line-height: 1.55;
  color: rgb(148 163 184);
  text-align: center;
}

.auth-legal-footer__link {
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  font: inherit;
  color: rgb(79 70 229);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
}

.auth-legal-footer__link:hover {
  color: rgb(67 56 202);
}
</style>
