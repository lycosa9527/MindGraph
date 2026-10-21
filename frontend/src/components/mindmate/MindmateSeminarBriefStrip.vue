<script setup lang="ts">
/**
 * Left-edge brief handle. Click scrolls the transcript to the seminar info card.
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables'

const props = defineProps<{
  topic: string
  goals: string[]
}>()

const emit = defineEmits<{
  (e: 'locate'): void
}>()

const { t } = useLanguage()

const ariaLabel = computed(() => {
  const topic = props.topic.trim()
  if (topic) {
    return topic
  }
  return t('mindmate.home.brief.locate')
})
</script>

<template>
  <div
    v-if="topic || goals.length"
    class="mm-brief-rail"
  >
    <button
      type="button"
      class="mm-brief-rail__handle"
      :aria-label="ariaLabel"
      :title="t('mindmate.home.brief.locate')"
      @click="emit('locate')"
    >
      <svg
        class="mm-brief-rail__flag"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id="mm-brief-flag-fill"
            x1="8"
            y1="4"
            x2="18"
            y2="12"
            gradientUnits="userSpaceOnUse"
          >
            <stop
              offset="0%"
              stop-color="#f7f5ff"
            />
            <stop
              offset="100%"
              stop-color="#c9c2fb"
            />
          </linearGradient>
        </defs>
        <path
          d="M8 3.4v17.2"
          fill="none"
          stroke="#5b4fe8"
          stroke-width="2.2"
          stroke-linecap="round"
        />
        <path
          d="M8.1 4.3h8.4L14.2 7.6l2.3 3.3H8.1z"
          fill="url(#mm-brief-flag-fill)"
          stroke="#5b4fe8"
          stroke-width="1.7"
          stroke-linejoin="round"
        />
      </svg>
      <span
        v-if="goals.length"
        class="mm-brief-rail__badge"
      >
        {{ goals.length }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.mm-brief-rail {
  position: absolute;
  left: 8px;
  top: 12px;
  z-index: 45;
  display: flex;
  align-items: flex-start;
  pointer-events: none;
}

.mm-brief-rail__handle {
  pointer-events: auto;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  margin: 0;
  padding: 0;
  border: 1.5px solid #6d64f2;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(109, 100, 242, 0.18), rgba(255, 255, 255, 0) 58%), #fff;
  box-shadow:
    0 1px 2px rgba(80, 70, 229, 0.08),
    0 8px 18px rgba(80, 70, 229, 0.14);
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.mm-brief-rail__handle:hover {
  transform: translateY(-1px);
  border-color: #5b4fe8;
  box-shadow:
    0 1px 2px rgba(80, 70, 229, 0.1),
    0 10px 22px rgba(80, 70, 229, 0.2);
}

.mm-brief-rail__flag {
  width: 16px;
  height: 16px;
  display: block;
}

.mm-brief-rail__badge {
  position: absolute;
  right: -7px;
  bottom: -6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 3px;
  box-sizing: border-box;
  border-radius: 999px;
  border: 2px solid #fff;
  background: #5b4fe8;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 2px 6px rgba(91, 79, 232, 0.35);
}
</style>
