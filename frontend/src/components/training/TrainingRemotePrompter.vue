<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import { useLanguage } from '@/composables'

const props = defineProps<{
  text: string
  resetKey: string
}>()

const { t } = useLanguage()
const scroller = ref<HTMLElement | null>(null)

watch(
  () => props.resetKey,
  () => {
    void nextTick(() => {
      if (scroller.value) scroller.value.scrollTop = 0
    })
  }
)
</script>

<template>
  <section
    class="prompter"
    :aria-label="t('training.builder.notes')"
  >
    <p class="prompter__kicker">{{ t('training.builder.notes') }}</p>
    <div
      ref="scroller"
      class="prompter__scroll"
    >
      <p
        v-if="text"
        class="prompter__body"
      >
        {{ text }}
      </p>
      <p
        v-else
        class="prompter__empty"
      >
        {{ t('training.remoteNotesEmpty') }}
      </p>
    </div>
  </section>
</template>

<style scoped>
.prompter {
  display: flex;
  min-height: 0;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  background: #1c1917;
  color: #fafaf9;
}
.prompter__kicker {
  flex-shrink: 0;
  margin: 0;
  padding: 0.55rem 0.85rem 0.35rem;
  color: #a8a29e;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.prompter__scroll {
  min-height: 0;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0 0.9rem 1rem;
  scrollbar-width: thin;
}
.prompter__body {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 550;
  line-height: 1.55;
  white-space: pre-wrap;
}
.prompter__empty {
  margin: 0;
  color: #78716c;
  font-size: 1rem;
}
</style>
