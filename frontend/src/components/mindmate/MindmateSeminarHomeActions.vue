<script setup lang="ts">
/**
 * Starters shown on the MindMate home screen while 群聊研讨 is selected.
 */
import I18nText from '@/components/common/I18nText.vue'

const emit = defineEmits<{
  (e: 'start'): void
  (e: 'invite'): void
  (e: 'history'): void
}>()
</script>

<template>
  <div class="mm-seminar-home">
    <div class="mm-seminar-home__label">
      <I18nText
        k="mindmate.home.seminarSuggestLabel"
        align="center"
      />
    </div>
    <div class="mm-seminar-home__list">
      <button
        type="button"
        class="mm-seminar-home__chip"
        @click="emit('start')"
      >
        <I18nText
          k="mindmate.home.seminarSuggestStart"
          dense
        />
      </button>
      <button
        type="button"
        class="mm-seminar-home__chip"
        @click="emit('invite')"
      >
        <I18nText
          k="mindmate.home.seminarSuggestJoin"
          dense
        />
      </button>
      <button
        type="button"
        class="mm-seminar-home__chip"
        @click="emit('history')"
      >
        <I18nText
          k="mindmate.home.seminarSuggestHistory"
          dense
        />
      </button>
    </div>
  </div>
</template>

<style scoped>
.mm-seminar-home__label {
  margin-bottom: 8px;
  font-size: 13px;
  color: #9ca3af;
  text-align: center;
}

.mm-seminar-home__list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.mm-seminar-home__chip {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 14px;
  line-height: 1.4;
  color: #111827;
  cursor: pointer;
}

.mm-seminar-home__chip:hover {
  background: #f9fafb;
}

:global(.dark) .mm-seminar-home__chip {
  background: #1f2937;
  border-color: #374151;
  color: #f9fafb;
}

:global(.dark) .mm-seminar-home__chip:hover {
  background: #111827;
}
</style>
