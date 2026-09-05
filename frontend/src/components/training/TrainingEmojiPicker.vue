<script setup lang="ts">
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables'
import { TRAINING_EMOJI_PAGES } from '@/config/trainingMarkPalettes'

const emit = defineEmits<{
  pick: [glyph: string]
}>()

const { t } = useLanguage()
const pageId = ref(TRAINING_EMOJI_PAGES[0]?.id || 'common')
const page = computed(
  () => TRAINING_EMOJI_PAGES.find((item) => item.id === pageId.value) || TRAINING_EMOJI_PAGES[0]
)
</script>

<template>
  <div class="emoji-picker">
    <div
      class="emoji-picker__tabs"
      role="tablist"
    >
      <button
        v-for="item in TRAINING_EMOJI_PAGES"
        :key="item.id"
        type="button"
        class="emoji-picker__tab"
        :class="{ 'is-on': item.id === pageId }"
        role="tab"
        :aria-selected="item.id === pageId"
        @click="pageId = item.id"
      >
        {{ t(item.labelKey) }}
      </button>
    </div>
    <div
      class="emoji-picker__grid"
      role="tabpanel"
    >
      <button
        v-for="glyph in page?.glyphs || []"
        :key="glyph"
        type="button"
        class="emoji-picker__cell"
        @click="emit('pick', glyph)"
      >
        {{ glyph }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.emoji-picker {
  display: flex;
  width: 14.5rem;
  flex-direction: column;
  gap: 0.45rem;
}
.emoji-picker__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.2rem;
}
.emoji-picker__tab {
  border: 1px solid #e7e5e4;
  background: #fff;
  color: #57534e;
  padding: 0.15rem 0.4rem;
  font-size: 0.68rem;
  cursor: pointer;
}
.emoji-picker__tab.is-on {
  border-color: #1c1917;
  background: #1c1917;
  color: #fafaf9;
}
.emoji-picker__grid {
  display: grid;
  grid-template-columns: repeat(8, 1.55rem);
  gap: 0.15rem;
}
.emoji-picker__cell {
  width: 1.55rem;
  height: 1.55rem;
  border: 1px solid #e7e5e4;
  background: #fff;
  cursor: pointer;
}
.emoji-picker__cell:hover {
  border-color: #1c1917;
}
</style>
