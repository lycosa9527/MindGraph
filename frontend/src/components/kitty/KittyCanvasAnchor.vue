<script setup lang="ts">
/**
 * Kitty entry on canvas: FAB (desktop-style) or inline pill (e.g. mobile under MindGraph).
 * Set ``interactive=false`` on desktop when the control is only a mobile-session status chip.
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import type { KittyAgentState } from '@/composables/kitty/useKittyAgent'

const props = withDefaults(
  defineProps<{
    visible: boolean
    state: KittyAgentState
    /** `fab` = fixed lower-left; `inline` = flows in layout (e.g. under title). */
    variant?: 'fab' | 'inline'
    /**
     * When variant is inline: full-width pill vs compact strip for toolbar rows
     * (e.g. beside MindGraph title, vertically centered).
     */
    inlineCompact?: boolean
    /** When false, renders a non-focusable status element (no open / reconnect actions). */
    interactive?: boolean
  }>(),
  { variant: 'fab', inlineCompact: false, interactive: true }
)

const { t } = useLanguage()

const emit = defineEmits<{
  click: []
}>()

const statusDotClass = computed(() => {
  switch (props.state) {
    case 'error':
      return 'kitty-voice-status--error'
    case 'connecting':
      return 'kitty-voice-status--connecting'
    case 'listening':
      return 'kitty-voice-status--listening'
    case 'speaking':
      return 'kitty-voice-status--speaking'
    case 'active':
      return 'kitty-voice-status--active'
    default:
      return 'kitty-voice-status--idle'
  }
})

const statusSubtitle = computed(() => {
  if (!props.interactive) {
    return t('canvas.kittyMobileIndicatorHint')
  }
  switch (props.state) {
    case 'error':
      return '连接异常 · 点击重试'
    case 'connecting':
      return '连接中…'
    case 'listening':
      return '正在聆听'
    case 'speaking':
      return '正在回复'
    case 'active':
      return '已连接 · 点击使用'
    default:
      return '语音与图示助手 · 点击打开'
  }
})

const ariaLabel = computed(() => {
  if (!props.interactive) {
    return t('canvas.kittyMobileIndicatorAria')
  }
  switch (props.state) {
    case 'error':
      return 'Kitty 智能体，连接异常，点击打开'
    case 'connecting':
      return 'Kitty 智能体，连接中，点击打开'
    case 'listening':
      return 'Kitty 智能体，正在聆听，点击打开'
    case 'speaking':
      return 'Kitty 智能体，正在回复，点击打开'
    case 'active':
      return 'Kitty 智能体，已连接，点击打开'
    default:
      return 'Kitty 智能体，点击连接或打开面板'
  }
})

const inlineTitle = computed(() =>
  props.interactive ? 'Kitty 智能体' : t('canvas.kittyMobileIndicatorTitle')
)

const fabShellClass = computed(() => {
  const base =
    'kitty-anchor fixed z-[60] w-14 h-14 rounded-full shadow-lg bg-white border-2 border-gray-200 dark:bg-gray-800 dark:border-gray-600 flex items-center justify-center text-2xl select-none'
  if (props.interactive) {
    return `${base} touch-manipulation hover:border-violet-300 dark:hover:border-violet-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2`
  }
  return `${base} pointer-events-none cursor-default`
})

const inlineShellClass = computed(() => {
  const base =
    'kitty-inline flex items-center gap-2.5 pl-3 pr-3 py-2 rounded-xl border-2 border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-sm text-left select-none'
  if (props.interactive) {
    return `${base} touch-manipulation active:bg-gray-50 dark:active:bg-gray-700/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-1`
  }
  return `${base} pointer-events-none cursor-default`
})
</script>

<template>
  <Transition :name="variant === 'inline' ? 'kitty-inline-pop' : 'kitty-anchor-pop'">
    <button
      v-if="visible && variant === 'fab' && interactive"
      type="button"
      :class="fabShellClass"
      :style="{
        left: 'max(12px, env(safe-area-inset-left))',
        bottom: 'max(12px, env(safe-area-inset-bottom))',
      }"
      :aria-label="ariaLabel"
      :title="ariaLabel"
      @click="emit('click')"
    >
      <span
        class="kitty-anchor__dot kitty-voice-status"
        :class="statusDotClass"
        aria-hidden="true"
      />
      <span
        class="relative z-0"
        :class="{
          'kitty-anchor__emoji--pulse': state === 'listening' || state === 'speaking',
        }"
        >🐈‍⬛</span
      >
    </button>

    <div
      v-else-if="visible && variant === 'fab' && !interactive"
      role="status"
      :class="fabShellClass"
      :style="{
        left: 'max(12px, env(safe-area-inset-left))',
        bottom: 'max(12px, env(safe-area-inset-bottom))',
      }"
      :aria-label="ariaLabel"
      :title="ariaLabel"
      tabindex="-1"
    >
      <span
        class="kitty-anchor__dot kitty-voice-status"
        :class="statusDotClass"
        aria-hidden="true"
      />
      <span
        class="relative z-0"
        :class="{
          'kitty-anchor__emoji--pulse': state === 'listening' || state === 'speaking',
        }"
        >🐈‍⬛</span
      >
    </div>

    <button
      v-else-if="visible && variant === 'inline' && interactive"
      type="button"
      :class="[
        inlineShellClass,
        inlineCompact
          ? 'w-auto max-w-[min(15rem,46vw)] shrink-0 self-center'
          : 'w-full max-w-md mx-auto',
      ]"
      :aria-label="ariaLabel"
      :title="ariaLabel"
      @click="emit('click')"
    >
      <span
        class="kitty-inline__dot kitty-voice-status shrink-0"
        :class="statusDotClass"
        aria-hidden="true"
      />
      <span
        class="text-xl leading-none shrink-0"
        :class="{
          'kitty-anchor__emoji--pulse': state === 'listening' || state === 'speaking',
        }"
        >🐈‍⬛</span
      >
      <div class="min-w-0 flex-1">
        <div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {{ inlineTitle }}
        </div>
        <div class="text-xs text-gray-500 dark:text-gray-400 truncate">
          {{ statusSubtitle }}
        </div>
      </div>
    </button>

    <div
      v-else-if="visible && variant === 'inline' && !interactive"
      role="status"
      tabindex="-1"
      :class="[
        inlineShellClass,
        inlineCompact
          ? 'w-auto max-w-[min(15rem,46vw)] shrink-0 self-center'
          : 'w-full max-w-md mx-auto',
      ]"
      :aria-label="ariaLabel"
      :title="ariaLabel"
    >
      <span
        class="kitty-inline__dot kitty-voice-status shrink-0"
        :class="statusDotClass"
        aria-hidden="true"
      />
      <span
        class="text-xl leading-none shrink-0"
        :class="{
          'kitty-anchor__emoji--pulse': state === 'listening' || state === 'speaking',
        }"
        >🐈‍⬛</span
      >
      <div class="min-w-0 flex-1">
        <div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {{ inlineTitle }}
        </div>
        <div class="text-xs text-gray-500 dark:text-gray-400 truncate">
          {{ statusSubtitle }}
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* FAB pop (lower-left) */
.kitty-anchor-pop-enter-active {
  transition:
    transform 0.38s cubic-bezier(0.34, 1.45, 0.64, 1),
    opacity 0.28s ease-out;
}

.kitty-anchor-pop-leave-active {
  transition:
    transform 0.22s ease-in,
    opacity 0.2s ease-in;
}

.kitty-anchor-pop-enter-from {
  transform: translate(-18px, 16px) scale(0.55);
  opacity: 0;
}

.kitty-anchor-pop-leave-to {
  transform: translate(-8px, 8px) scale(0.85);
  opacity: 0;
}

/* Inline strip under MindGraph */
.kitty-inline-pop-enter-active {
  transition:
    transform 0.32s cubic-bezier(0.34, 1.45, 0.64, 1),
    opacity 0.24s ease-out;
}

.kitty-inline-pop-leave-active {
  transition:
    transform 0.2s ease-in,
    opacity 0.18s ease-in;
}

.kitty-inline-pop-enter-from {
  transform: translateY(-10px) scale(0.96);
  opacity: 0;
}

.kitty-inline-pop-leave-to {
  transform: translateY(-4px) scale(0.98);
  opacity: 0;
}

.kitty-anchor__dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 11px;
  height: 11px;
  border-radius: 9999px;
  border: 2px solid #fff;
  box-sizing: border-box;
  z-index: 1;
}

.dark .kitty-anchor__dot {
  border-color: rgb(31 41 55);
}

.kitty-inline__dot {
  width: 10px;
  height: 10px;
  border-radius: 9999px;
  border: 2px solid #fff;
  box-sizing: border-box;
}

.dark .kitty-inline__dot {
  border-color: rgb(31 41 55);
}

.kitty-voice-status--idle {
  background-color: rgb(156 163 175);
}

.kitty-voice-status--connecting {
  background-color: rgb(245 158 11);
  animation: kitty-dot-pulse 1s ease-in-out infinite;
}

.kitty-voice-status--active {
  background-color: rgb(34 197 94);
}

.kitty-voice-status--listening {
  background-color: rgb(59 130 246);
  animation: kitty-dot-pulse 0.85s ease-in-out infinite;
}

.kitty-voice-status--speaking {
  background-color: rgb(139 92 246);
  animation: kitty-dot-pulse 0.75s ease-in-out infinite;
}

.kitty-voice-status--error {
  background-color: rgb(239 68 68);
}

@keyframes kitty-dot-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.15);
    opacity: 0.85;
  }
}

.kitty-anchor__emoji--pulse {
  animation: kitty-emoji-pulse 1.2s ease-in-out infinite;
}

@keyframes kitty-emoji-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.06);
  }
}
</style>
