<script setup lang="ts">
/**
 * MindMate home segmented control: personal chat vs group seminar.
 */
import { MessageCircle, Users } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'

defineProps<{
  mode: 'dialogue' | 'seminar'
}>()

const emit = defineEmits<{
  (e: 'update:mode', mode: 'dialogue' | 'seminar'): void
}>()

const { t } = useLanguage()
</script>

<template>
  <div
    class="mm-home-mode"
    role="tablist"
    :aria-label="t('mindmate.home.modeSwitchLabel')"
  >
    <button
      type="button"
      role="tab"
      class="mm-home-mode__btn"
      :class="{ 'is-active': mode === 'dialogue' }"
      :aria-selected="mode === 'dialogue'"
      @click="emit('update:mode', 'dialogue')"
    >
      <MessageCircle
        class="mm-home-mode__icon"
        :size="16"
        aria-hidden="true"
      />
      <I18nText
        k="mindmate.home.modeDialogue"
        dense
      />
    </button>
    <button
      type="button"
      role="tab"
      class="mm-home-mode__btn"
      :class="{ 'is-active': mode === 'seminar' }"
      :aria-selected="mode === 'seminar'"
      @click="emit('update:mode', 'seminar')"
    >
      <Users
        class="mm-home-mode__icon"
        :size="16"
        aria-hidden="true"
      />
      <I18nText
        k="mindmate.home.modeSeminar"
        dense
      />
    </button>
  </div>
</template>

<style scoped>
.mm-home-mode {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 16px;
  padding: 4px;
  border-radius: 999px;
  border: 1px solid #e7e5e4;
  background: #fff;
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.04);
}

.mm-home-mode__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  border-radius: 999px;
  padding: 7px 14px;
  font-size: 14px;
  line-height: 1.2;
  color: #78716c;
  cursor: pointer;
}

.mm-home-mode__icon {
  flex: 0 0 auto;
}

.mm-home-mode__btn.is-active {
  background: linear-gradient(90deg, #6366f1 0%, #7c3aed 100%);
  color: #fff;
}

.mm-home-mode__btn:hover:not(.is-active) {
  background: #f5f5f4;
  color: #44403c;
}

:global(.dark) .mm-home-mode {
  border-color: #44403c;
  background: #1c1917;
  box-shadow: none;
}

:global(.dark) .mm-home-mode__btn {
  color: #a8a29e;
}

:global(.dark) .mm-home-mode__btn:hover:not(.is-active) {
  background: #292524;
  color: #e7e5e4;
}

:global(.dark) .mm-home-mode__btn.is-active {
  background: linear-gradient(90deg, #6366f1 0%, #7c3aed 100%);
  color: #fff;
}
</style>
