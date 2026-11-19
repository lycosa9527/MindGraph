<script setup lang="ts">
/**
 * Workbench card: glasses photos, with the OCR diagram and the original image.
 */
import { ref } from 'vue'

import LearningSpaceGlassesTree from '@/components/learningSpace/LearningSpaceGlassesTree.vue'
import { useLanguage } from '@/composables'
import { formatLsDateTime } from '@/composables/learningSpace/lsHelpers'
import {
  type GlassesCapture,
  useLearningSpaceGlassesCaptures,
} from '@/composables/learningSpace/useLearningSpaceGlassesCaptures'

type SheetView = 'spec' | 'photo'

const { t } = useLanguage()
const { captures, loading, failed } = useLearningSpaceGlassesCaptures()
const viewById = ref<Record<number, SheetView>>({})

function viewOf(row: GlassesCapture): SheetView {
  return viewById.value[row.id] ?? 'spec'
}

function setView(id: number, view: SheetView) {
  viewById.value = { ...viewById.value, [id]: view }
}

function meta(row: GlassesCapture): string {
  const parts = [row.class_name.trim(), formatLsDateTime(row.created_at)].filter(
    (part) => part && part !== '—'
  )
  return parts.join(' · ')
}
</script>

<template>
  <section class="ls-glasses">
    <div class="ls-section-title">
      <h2><I18nText k="learningSpace.glassesCardTitle" /></h2>
    </div>
    <p class="ls-glasses__hint"><I18nText k="learningSpace.glassesCardHint" /></p>
    <p
      v-if="loading"
      class="ls-muted"
    >
      <I18nText k="common.loading" />
    </p>
    <p
      v-else-if="failed"
      class="ls-muted"
    >
      <I18nText k="learningSpace.glassesLoadError" />
    </p>
    <p
      v-else-if="!captures.length"
      class="ls-muted"
    >
      <I18nText k="learningSpace.glassesEmpty" />
    </p>
    <div
      v-else
      class="ls-glasses__grid"
    >
      <article
        v-for="row in captures"
        :key="row.id"
        class="ls-glasses__card"
      >
        <header class="ls-glasses__head">
          <div>
            <h3 class="ls-glasses__name">
              {{ row.student_name.trim() || '' }}
              <I18nText
                v-if="!row.student_name.trim()"
                k="learningSpace.glassesUnnamed"
              />
            </h3>
            <p
              v-if="meta(row)"
              class="ls-glasses__meta"
            >
              {{ meta(row) }}
            </p>
          </div>
          <div
            class="ls-glasses__switch"
            role="radiogroup"
            :aria-label="t('learningSpace.glassesCardTitle')"
          >
            <button
              type="button"
              role="radio"
              :aria-checked="viewOf(row) === 'spec'"
              :class="{ 'ls-glasses__switch-btn--on': viewOf(row) === 'spec' }"
              class="ls-glasses__switch-btn"
              @click="setView(row.id, 'spec')"
            >
              <I18nText k="learningSpace.glassesViewSpec" />
            </button>
            <button
              type="button"
              role="radio"
              :aria-checked="viewOf(row) === 'photo'"
              :class="{ 'ls-glasses__switch-btn--on': viewOf(row) === 'photo' }"
              class="ls-glasses__switch-btn"
              @click="setView(row.id, 'photo')"
            >
              <I18nText k="learningSpace.glassesViewPhoto" />
            </button>
          </div>
        </header>
        <div class="ls-glasses__stage">
          <img
            v-if="viewOf(row) === 'photo' && row.image_path"
            class="ls-glasses__photo"
            :src="row.image_path"
            alt=""
          />
          <p
            v-else-if="row.ocr_status === 'pending'"
            class="ls-muted"
          >
            <I18nText k="learningSpace.glassesPending" />
          </p>
          <p
            v-else-if="row.ocr_status === 'failed' || !row.spec"
            class="ls-muted"
          >
            <I18nText k="learningSpace.glassesFailed" />
          </p>
          <div
            v-else
            class="ls-glasses__spec"
          >
            <p class="ls-glasses__topic">{{ row.spec.topic }}</p>
            <ul class="ls-glasses-tree">
              <LearningSpaceGlassesTree
                v-for="(child, index) in row.spec.children"
                :key="`${child.text}-${index}`"
                :text="child.text"
                :children="child.children"
              />
            </ul>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.ls-glasses {
  margin-top: 1.5rem;
}

.ls-glasses__hint {
  margin: -0.35rem 0 0.9rem;
  color: var(--ls-slate);
  font-size: 0.85rem;
}

.ls-glasses__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.95rem;
}

.ls-glasses__card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 1.05rem;
  border: 1px solid var(--ls-border);
  border-radius: var(--ls-radius);
  background: var(--ls-surface);
  box-shadow: var(--ls-shadow);
}

.ls-glasses__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.ls-glasses__name {
  margin: 0;
  font-size: 1rem;
  font-weight: 750;
}

.ls-glasses__meta {
  margin: 0.25rem 0 0;
  color: var(--ls-slate);
  font-size: 0.78rem;
}

.ls-glasses__switch {
  display: inline-flex;
  flex-shrink: 0;
  padding: 0.15rem;
  border-radius: 999px;
  background: var(--ls-indigo-soft);
}

.ls-glasses__switch-btn {
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--ls-ink);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.28rem 0.65rem;
  cursor: pointer;
}

.ls-glasses__switch-btn--on {
  background: var(--ls-indigo);
  color: #fff;
}

.ls-glasses__stage {
  min-height: 8rem;
  overflow: auto;
}

.ls-glasses__photo {
  display: block;
  width: 100%;
  max-height: 18rem;
  object-fit: contain;
  border-radius: 0.6rem;
  background: var(--ls-bg);
}

.ls-glasses__topic {
  margin: 0 0 0.45rem;
  font-weight: 750;
}

.ls-glasses__spec > .ls-glasses-tree {
  margin: 0;
  padding-left: 1.1rem;
}

@media (max-width: 860px) {
  .ls-glasses__grid {
    grid-template-columns: 1fr;
  }
}
</style>
