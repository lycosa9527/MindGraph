<script setup lang="ts">
/**
 * SwissWarningModal — reusable Swiss Design warning dialog.
 *
 * Design: Swiss International Style (stone neutrals, geek-red accent bar,
 * hard border + offset shadow, dual actions).
 *
 * Defaults: FEATURE_TEST_SERVER_BANNER (test env once/day + on login +
 * always on /auth; jump to www.mindspringedu.com). See App.vue.
 *
 * School lockout: pass copy props, showJump=false, countTestServerDay=false.
 */
import { computed, nextTick, onUnmounted, useTemplateRef, watch } from 'vue'

import { ArrowUpRight, TriangleAlert } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { BlackCat } from '@/utils/mascot/blackCat'
import { markTestServerBannerShownToday } from '@/utils/testServerBanner'

const PRODUCTION_URL = 'https://www.mindspringedu.com'

const visible = defineModel<boolean>({ required: true })

const props = withDefaults(
  defineProps<{
    badge?: string
    envLabel?: string
    title?: string
    body?: string
    host?: string
    confirmLabel?: string
    jumpLabel?: string
    showJump?: boolean
    countTestServerDay?: boolean
  }>(),
  {
    showJump: true,
    countTestServerDay: true,
  }
)

const emit = defineEmits<{
  confirm: []
}>()

const { t } = useLanguage()
const badgeText = computed(() => props.badge ?? t('app.testServer.badge'))
const envText = computed(() => props.envLabel ?? 'ENVIRONMENT')
const titleText = computed(() => props.title ?? t('app.testServer.title'))
const bodyText = computed(() => props.body ?? t('app.testServer.body'))
const hostText = computed(() => {
  if (props.host !== undefined) {
    return props.host
  }
  return props.showJump ? t('app.testServer.productionHost') : ''
})
const confirmText = computed(() => props.confirmLabel ?? t('app.testServer.confirm'))
const jumpText = computed(() => props.jumpLabel ?? t('app.testServer.jump'))
const kittyHostRef = useTemplateRef<HTMLDivElement>('kittyHostRef')
let kittyMascot: BlackCat | null = null

function destroyKittyMascot(): void {
  kittyMascot?.destroy()
  kittyMascot = null
}

async function mountKittyMascot(): Promise<void> {
  destroyKittyMascot()
  await nextTick()
  const host = kittyHostRef.value
  if (!host) {
    return
  }
  kittyMascot = new BlackCat()
  kittyMascot.init(host)
  if (kittyMascot.container) {
    kittyMascot.container.title = ''
    kittyMascot.container.removeAttribute('title')
  }
  kittyMascot.setState('idle')
}

watch(
  visible,
  async (isOpen) => {
    if (typeof document === 'undefined') {
      return
    }
    if (isOpen) {
      if (props.countTestServerDay) {
        markTestServerBannerShownToday()
      }
      document.body.style.overflow = 'hidden'
      await mountKittyMascot()
      return
    }
    destroyKittyMascot()
    document.body.style.overflow = ''
  },
  { immediate: true }
)

onUnmounted(() => {
  destroyKittyMascot()
  if (typeof document !== 'undefined') {
    document.body.style.overflow = ''
  }
})

function handleConfirm(): void {
  emit('confirm')
  visible.value = false
}

function handleJump(): void {
  window.location.assign(PRODUCTION_URL)
}
</script>

<template>
  <SwissGlassCard
    v-model="visible"
    :ribbon="t('swissGlass.hero.warning.ribbon')"
    :title="titleText"
    :line1="bodyText"
    :icon="TriangleAlert"
    :show-close="false"
    persistent
    overlay-class="swm-overlay"
  >
    <p
      v-if="hostText"
      class="swm-host"
    >
      <span class="swm-host-value">{{ hostText }}</span>
    </p>
    <div class="swm-meta">
      <span class="swm-badge">{{ badgeText }}</span>
      <span class="swm-rule" />
      <span class="swm-env">{{ envText }}</span>
    </div>
    <template #footer>
      <div class="swiss-glass-footer swm-actions">
        <button
          v-if="showJump"
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </button>
        <div class="swm-jump-wrap">
          <div
            ref="kittyHostRef"
            class="swm-kitty-perch"
            aria-hidden="true"
          />
          <button
            type="button"
            class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
            @click="showJump ? handleJump() : handleConfirm()"
          >
            <span>{{ showJump ? jumpText : confirmText }}</span>
            <ArrowUpRight
              v-if="showJump"
              class="swm-btn-icon"
              :size="16"
              :stroke-width="2"
            />
          </button>
        </div>
      </div>
    </template>
  </SwissGlassCard>
</template>

<style scoped>
.swm-overlay {
  z-index: 10050;
}

.swm-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.swm-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--swiss-surface, #ffffff);
  background: var(--swiss-geek-red, #e30613);
  line-height: 1.4;
}

.swm-rule {
  flex: 1;
  height: 1px;
  background: var(--swiss-border-strong, #d6d3d1);
}

.swm-env {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--swiss-muted, #78716c);
}

.swm-host {
  display: flex;
  align-items: baseline;
  margin: 0 0 16px;
  padding: 12px 8px 12px 16px;
  border-top: 1px solid var(--swiss-border, #e7e5e4);
  border-bottom: 1px solid var(--swiss-border, #e7e5e4);
  background: var(--swiss-inset, #fafaf9);
}

.swm-host-value {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--swiss-ink, #1c1917);
  font-variant-numeric: tabular-nums;
}

.swm-actions {
  align-items: flex-end;
  padding-top: 28px;
}

.swm-jump-wrap {
  position: relative;
  display: inline-flex;
  overflow: visible;
}

.swm-kitty-perch {
  position: absolute;
  right: 8px;
  bottom: calc(100% - 6px);
  z-index: 1;
  width: 44px;
  height: 56px;
  pointer-events: none;
  line-height: 0;
  overflow: visible;
  filter: drop-shadow(0 1px 1px rgba(28, 25, 23, 0.2));
}

.swm-kitty-perch :deep(.black-cat-container) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  cursor: default;
}

.swm-kitty-perch :deep(.black-cat-container .kitty-svg) {
  width: 100%;
  height: 100%;
  overflow: visible;
}

.swm-btn-icon {
  flex-shrink: 0;
}
</style>

<style>
.swm-overlay {
  z-index: 10050;
}
</style>
