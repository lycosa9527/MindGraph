<script setup lang="ts">
/**
 * October update: what changed for people using the product since August.
 */
import { Sparkles } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'

const visible = defineModel<boolean>('visible', { default: false })

const sections = [
  { title: 'training.october.canvas', body: 'training.october.canvasBody' },
  { title: 'training.october.explain', body: 'training.october.explainBody' },
  { title: 'training.october.account', body: 'training.october.accountBody' },
  { title: 'training.october.learning', body: 'training.october.learningBody' },
  { title: 'training.october.course', body: 'training.october.courseBody' },
  { title: 'training.october.talk', body: 'training.october.talkBody' },
  { title: 'training.october.school', body: 'training.october.schoolBody' },
]

const { t } = useLanguage()

function sectionItems(bodyKey: string): { lead: string; text: string }[] {
  return t(bodyKey)
    .split('\n')
    .map((line) => {
      const trimmed = line.trim()
      const cut = trimmed.indexOf('|')
      if (cut < 0) return { lead: '', text: trimmed }
      return { lead: trimmed.slice(0, cut).trim(), text: trimmed.slice(cut + 1).trim() }
    })
    .filter((item) => item.lead || item.text)
}
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('training.october.ribbon')"
    ribbon-key="training.october.ribbon"
    :title="t('training.october.title')"
    title-key="training.october.title"
    :line1="t('training.october.lead')"
    line1-key="training.october.lead"
    :icon="Sparkles"
    width="min(40rem, 94vw)"
    dialog-class="october-update-dialog"
  >
    <div class="october">
      <section
        v-for="section in sections"
        :key="section.title"
        class="october__section"
      >
        <h3><I18nText :k="section.title" /></h3>
        <ul class="october__list">
          <li
            v-for="(item, index) in sectionItems(section.body)"
            :key="`${section.title}-${index}`"
          >
            <strong v-if="item.lead">{{ item.lead }}</strong>
            {{ item.text }}
          </li>
        </ul>
      </section>
    </div>
  </SwissGlassDialog>
</template>

<style scoped>
.october {
  display: flex;
  max-height: min(52vh, 28rem);
  flex-direction: column;
  gap: 0.9rem;
  overflow: auto;
  padding-right: 0.15rem;
}
.october__section h3 {
  margin: 0 0 0.35rem;
  color: #1c1917;
  font-size: 0.92rem;
  font-weight: 700;
}
.october__list {
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
  margin: 0;
  padding: 0 0 0 1.15rem;
}
.october__list li {
  color: #57534e;
  font-size: 0.8rem;
  line-height: 1.5;
}
.october__list strong {
  color: #1c1917;
  font-weight: 700;
}
</style>
