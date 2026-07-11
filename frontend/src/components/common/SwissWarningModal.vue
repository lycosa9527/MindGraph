<script setup lang="ts">
/**
 * SwissWarningModal — reusable Swiss Design warning dialog.
 *
 * Design: Swiss International Style (stone neutrals, geek-red accent bar,
 * hard border + offset shadow, dual actions).
 *
 * Canonical name: SwissWarningModal
 * Path: @/components/common/SwissWarningModal.vue
 *
 * Reuse: import for any blocking notice that needs this chrome. Wire with
 * v-model; keep feature-flag / cadence logic in the parent.
 *
 * Current use: FEATURE_TEST_SERVER_BANNER (test env once/day + on login +
 * always on /auth; jump to mg.mindspringedu.com). See App.vue.
 */
import { nextTick, onUnmounted, useTemplateRef, watch } from 'vue'

import { ArrowUpRight } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { BlackCat } from '@/utils/mascot/blackCat'
import { markTestServerBannerShownToday } from '@/utils/testServerBanner'

const PRODUCTION_URL = 'https://mg.mindspringedu.com'

const visible = defineModel<boolean>({ required: true })

const { t } = useLanguage()
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
      // Count this calendar day as notified once the modal is shown.
      markTestServerBannerShownToday()
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
  visible.value = false
}

function handleJump(): void {
  window.location.assign(PRODUCTION_URL)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="swm-fade">
      <div
        v-if="visible"
        class="swm-overlay"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="swm-title"
        aria-describedby="swm-body"
      >
        <div class="swm-panel">
          <div
            class="swm-accent"
            aria-hidden="true"
          />

          <div class="swm-meta">
            <span class="swm-badge">{{ t('app.testServer.badge') }}</span>
            <span class="swm-rule" />
            <span class="swm-env">ENVIRONMENT</span>
          </div>

          <h2
            id="swm-title"
            class="swm-title"
          >
            {{ t('app.testServer.title') }}
          </h2>

          <p
            id="swm-body"
            class="swm-body"
          >
            {{ t('app.testServer.body') }}
          </p>

          <p class="swm-host">
            <span class="swm-host-value">{{ t('app.testServer.productionHost') }}</span>
          </p>

          <div class="swm-actions">
            <button
              type="button"
              class="swm-btn swm-btn-ghost"
              @click="handleConfirm"
            >
              {{ t('app.testServer.confirm') }}
            </button>
            <div class="swm-jump-wrap">
              <div
                ref="kittyHostRef"
                class="swm-kitty-perch"
                aria-hidden="true"
              />
              <button
                type="button"
                class="swm-btn swm-btn-solid"
                @click="handleJump"
              >
                <span>{{ t('app.testServer.jump') }}</span>
                <ArrowUpRight
                  class="swm-btn-icon"
                  :size="16"
                  :stroke-width="2"
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.swm-overlay {
  position: fixed;
  inset: 0;
  z-index: 10050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(28, 25, 23, 0.55);
  backdrop-filter: blur(2px);
}

.swm-panel {
  position: relative;
  width: min(420px, 100%);
  background: var(--swiss-surface, #ffffff);
  border: 1px solid var(--swiss-ink, #1c1917);
  box-shadow: 8px 8px 0 0 var(--swiss-ink, #1c1917);
  padding: 28px 28px 24px;
  overflow: visible;
}

.swm-accent {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--swiss-geek-red, #e30613);
}

.swm-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-left: 8px;
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

.swm-title {
  margin: 0 0 12px;
  padding-left: 8px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.15;
  color: var(--swiss-ink, #1c1917);
}

.swm-body {
  margin: 0 0 20px;
  padding-left: 8px;
  font-size: 14px;
  line-height: 1.55;
  color: var(--swiss-body, #44403c);
}

.swm-host {
  display: flex;
  align-items: baseline;
  margin: 0 0 28px;
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
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
  align-items: flex-end;
  padding-left: 8px;
  padding-top: 36px;
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

.swm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--swiss-ink, #1c1917);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.swm-btn-ghost {
  background: transparent;
  color: var(--swiss-ink, #1c1917);
}

.swm-btn-ghost:hover {
  background: var(--swiss-hover, #f5f5f4);
}

.swm-btn-solid {
  background: var(--swiss-ink, #1c1917);
  color: var(--swiss-surface, #ffffff);
}

.swm-btn-solid:hover {
  background: var(--swiss-geek-red, #e30613);
  border-color: var(--swiss-geek-red, #e30613);
}

.swm-btn-icon {
  flex-shrink: 0;
}

.swm-fade-enter-active,
.swm-fade-leave-active {
  transition: opacity 0.18s ease;
}

.swm-fade-enter-active .swm-panel,
.swm-fade-leave-active .swm-panel {
  transition:
    transform 0.18s ease,
    opacity 0.18s ease;
}

.swm-fade-enter-from,
.swm-fade-leave-to {
  opacity: 0;
}

.swm-fade-enter-from .swm-panel,
.swm-fade-leave-to .swm-panel {
  transform: translateY(6px);
  opacity: 0;
}

@media (max-width: 480px) {
  .swm-actions {
    flex-direction: column-reverse;
  }

  .swm-btn {
    width: 100%;
  }

  .swm-title {
    font-size: 24px;
  }
}
</style>
