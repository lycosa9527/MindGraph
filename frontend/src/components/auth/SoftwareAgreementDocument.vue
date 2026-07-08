<script setup lang="ts">
/**
 * Renders Terms + Privacy body (shared by modal and /privacy page).
 */
import type { SoftwareAgreementContent, SoftwareAgreementSection } from '@/content/authSoftwareAgreement'

defineProps<{
  agreement: SoftwareAgreementContent
  extraSections?: SoftwareAgreementSection[]
}>()
</script>

<template>
  <div class="sa-body">
    <p class="sa-preamble">
      {{ agreement.preamble }}
    </p>

    <section
      v-for="(section, idx) in agreement.sections"
      :key="`main-${idx}`"
      class="sa-section"
    >
      <h3 class="sa-section__title">
        {{ section.title }}
      </h3>
      <p
        v-for="(paragraph, pIdx) in section.paragraphs"
        :key="pIdx"
        class="sa-section__paragraph"
      >
        {{ paragraph }}
      </p>
    </section>

    <section
      v-for="(section, idx) in extraSections ?? []"
      :id="idx === 0 ? 'browser-extension' : undefined"
      :key="`extra-${idx}`"
      class="sa-section sa-section--extra"
    >
      <h3 class="sa-section__title">
        {{ section.title }}
      </h3>
      <p
        v-for="(paragraph, pIdx) in section.paragraphs"
        :key="pIdx"
        class="sa-section__paragraph"
      >
        {{ paragraph }}
      </p>
    </section>
  </div>
</template>

<style scoped>
.sa-body {
  color: rgb(41 37 36);
}

.sa-preamble {
  margin: 0 0 1.25rem;
  font-size: 0.9375rem;
  line-height: 1.65;
  color: rgb(68 64 60);
}

.sa-section + .sa-section {
  margin-top: 1.25rem;
}

.sa-section--extra {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgb(231 229 228);
}

.sa-section__title {
  margin: 0 0 0.5rem;
  font-size: 0.9375rem;
  font-weight: 600;
  line-height: 1.45;
  color: rgb(28 25 23);
}

.sa-section__paragraph {
  margin: 0 0 0.55rem;
  font-size: 0.875rem;
  line-height: 1.7;
  color: rgb(68 64 60);
}

.sa-section__paragraph:last-child {
  margin-bottom: 0;
}
</style>
