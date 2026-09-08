<script setup lang="ts">
/**
 * Frosted-glass hero for document / web / voice generate dialogs.
 */
import { computed } from 'vue'

import {
  GraduationCap,
  Hammer,
  Lightbulb,
  Link2,
  MessageSquare,
  Mic,
  PenLine,
  Sparkles,
  Upload,
} from '@lucide/vue'

import MindMapSidePanelCloseButton from '@/components/canvas/MindMapSidePanelCloseButton.vue'
import '@/components/canvas/aiGenerateGlass.css'
import { useLanguage } from '@/composables/core/useLanguage'

const props = withDefaults(
  defineProps<{
    variant:
      | 'doc'
      | 'web'
      | 'voice'
      | 'chat'
      | 'classroom'
      | 'learningSheet'
      | 'brainstorm'
      | 'oneSentence'
    showClose?: boolean
  }>(),
  { showClose: true }
)

const emit = defineEmits<{ close: [] }>()

const { t } = useLanguage()

const copy = computed(() => ({
  ribbon: t(`canvas.ribbon.aiHero.${props.variant}.ribbon`),
  title: t(`canvas.ribbon.aiHero.${props.variant}.title`),
  line1: t(`canvas.ribbon.aiHero.${props.variant}.line1`),
  line2: t(`canvas.ribbon.aiHero.${props.variant}.line2`),
}))
</script>

<template>
  <div
    class="ai-glass-hero"
    :class="`ai-glass-hero--${variant}`"
  >
    <div
      class="ai-glass-hero__icon"
      aria-hidden="true"
    >
      <div class="ai-glass-icon__plate">
        <svg
          v-if="variant === 'doc'"
          class="ai-glass-icon__glyph"
          viewBox="8 8 32 32"
          fill="none"
        >
          <path
            d="M10 14.5c0-2.2 1.8-4 4-4h12.2L34 18.2V33.5c0 2.2-1.8 4-4 4H14c-2.2 0-4-1.8-4-4v-19Z"
            fill="currentColor"
            fill-opacity="0.18"
            stroke="currentColor"
            stroke-width="2"
          />
          <path
            d="M26 10.8V18h7.4"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
          <path
            d="M16 24h12M16 29h8"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
        </svg>
        <svg
          v-else-if="variant === 'web'"
          class="ai-glass-icon__glyph"
          viewBox="8 8 32 32"
          fill="none"
        >
          <rect
            x="8"
            y="12"
            width="32"
            height="24"
            rx="6"
            fill="currentColor"
            fill-opacity="0.16"
            stroke="currentColor"
            stroke-width="2"
          />
          <circle
            cx="14"
            cy="18"
            r="1.6"
            fill="currentColor"
          />
          <circle
            cx="19"
            cy="18"
            r="1.6"
            fill="currentColor"
          />
          <circle
            cx="24"
            cy="18"
            r="1.6"
            fill="currentColor"
          />
          <path
            d="M16 28h16"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
        </svg>
        <svg
          v-else-if="variant === 'voice'"
          class="ai-glass-icon__glyph"
          viewBox="8 8 32 32"
          fill="none"
        >
          <path
            d="M10 16c0-3.3 2.7-6 6-6h10c3.3 0 6 2.7 6 6v8c0 3.3-2.7 6-6 6H20l-7 6v-6h-3c-3.3 0-6-2.7-6-6v-8Z"
            fill="currentColor"
            fill-opacity="0.16"
            stroke="currentColor"
            stroke-width="2"
          />
          <path
            d="M19 18v10M24 20v6M29 19v8"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
          />
        </svg>
        <svg
          v-else-if="variant === 'classroom'"
          class="ai-glass-icon__glyph"
          viewBox="8 8 32 32"
          fill="none"
        >
          <rect
            x="10"
            y="20"
            width="12.5"
            height="8"
            rx="4"
            fill="currentColor"
            fill-opacity="0.22"
            stroke="currentColor"
            stroke-width="1.8"
          />
          <path
            d="M22.5 24h4.6M22.5 24l6.4-8.4M22.5 24l6.4 8.4"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
          <rect
            x="26.2"
            y="11"
            width="11.2"
            height="6.8"
            rx="3.3"
            fill="currentColor"
            fill-opacity="0.2"
            stroke="currentColor"
            stroke-width="1.8"
          />
          <rect
            x="27.2"
            y="20.6"
            width="11.2"
            height="6.8"
            rx="3.3"
            fill="currentColor"
            fill-opacity="0.2"
            stroke="currentColor"
            stroke-width="1.8"
          />
          <rect
            x="26.2"
            y="30.2"
            width="11.2"
            height="6.8"
            rx="3.3"
            fill="currentColor"
            fill-opacity="0.2"
            stroke="currentColor"
            stroke-width="1.8"
          />
          <path
            d="M13.2 16.2c-3.4 2.8-3.6 9.4.4 13.2"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linecap="round"
            stroke-dasharray="2.2 2"
            opacity="0.7"
          />
        </svg>
        <svg
          v-else-if="variant === 'learningSheet'"
          class="ai-glass-icon__glyph"
          viewBox="8 8 32 32"
          fill="none"
        >
          <rect
            x="9"
            y="20"
            width="13"
            height="8"
            rx="4"
            fill="currentColor"
            fill-opacity="0.22"
            stroke="currentColor"
            stroke-width="1.8"
          />
          <path
            d="M22 24h5.2M22 24l6.6-8.2M22 24l6.6 8.2"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
          <rect
            x="26.5"
            y="11"
            width="12"
            height="7"
            rx="3.5"
            fill="currentColor"
            fill-opacity="0.2"
            stroke="currentColor"
            stroke-width="1.8"
          />
          <rect
            x="27.5"
            y="20.5"
            width="12"
            height="7"
            rx="3.5"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-dasharray="2.4 2.1"
          />
          <path
            d="M30.4 24h6.2"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            opacity="0.55"
          />
          <rect
            x="26.5"
            y="30"
            width="12"
            height="7"
            rx="3.5"
            fill="currentColor"
            fill-opacity="0.2"
            stroke="currentColor"
            stroke-width="1.8"
          />
        </svg>
        <Sparkles
          v-else-if="variant === 'brainstorm'"
          class="ai-glass-icon__glyph"
          :size="36"
          :stroke-width="2"
        />
        <PenLine
          v-else-if="variant === 'oneSentence'"
          class="ai-glass-icon__glyph"
          :size="34"
          :stroke-width="2"
        />
        <svg
          v-else
          class="ai-glass-icon__glyph"
          viewBox="8 8 32 32"
          fill="none"
        >
          <rect
            x="10"
            y="12"
            width="22"
            height="16"
            rx="5"
            fill="currentColor"
            fill-opacity="0.16"
            stroke="currentColor"
            stroke-width="2"
          />
          <rect
            x="16"
            y="30"
            width="22"
            height="8"
            rx="4"
            fill="currentColor"
            fill-opacity="0.12"
            stroke="currentColor"
            stroke-width="2"
          />
        </svg>
      </div>
      <span class="ai-glass-icon__badge">
        <Upload
          v-if="variant === 'doc'"
          :size="12"
          :stroke-width="2.4"
        />
        <Link2
          v-else-if="variant === 'web'"
          :size="12"
          :stroke-width="2.4"
        />
        <Mic
          v-else-if="variant === 'voice'"
          :size="12"
          :stroke-width="2.4"
        />
        <GraduationCap
          v-else-if="variant === 'classroom'"
          :size="12"
          :stroke-width="2.4"
        />
        <Hammer
          v-else-if="variant === 'learningSheet'"
          :size="12"
          :stroke-width="2.4"
        />
        <Lightbulb
          v-else-if="variant === 'brainstorm'"
          :size="12"
          :stroke-width="2.4"
        />
        <Sparkles
          v-else-if="variant === 'oneSentence'"
          :size="12"
          :stroke-width="2.4"
        />
        <MessageSquare
          v-else
          :size="12"
          :stroke-width="2.4"
        />
      </span>
    </div>

    <div class="ai-glass-hero__corner">
      <span class="ai-glass-hero__ribbon">{{ copy.ribbon }}</span>
      <MindMapSidePanelCloseButton
        v-if="showClose"
        @close="emit('close')"
      />
    </div>

    <h2 class="ai-glass-hero__title">{{ copy.title }}</h2>
    <p class="ai-glass-hero__lines">
      {{ copy.line1 }}<template v-if="copy.line2"><br />{{ copy.line2 }}</template>
    </p>
  </div>
</template>
