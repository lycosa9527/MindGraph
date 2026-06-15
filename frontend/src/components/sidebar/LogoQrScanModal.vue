<script setup lang="ts">
/**
 * Full-screen blurred overlay showing the public site URL as a QR code.
 * Opened when the sidebar logo is hovered (pointer devices).
 */
import { computed } from 'vue'

import { ElButton } from 'element-plus'

import { X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { usePublicSiteUrl } from '@/composables/core/usePublicSiteUrl'
import { APP_REFINED_SANS_STACK } from '@/utils/diagramNodeFontStack'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: []; hoverEnter: []; hoverLeave: [] }>()

const { t } = useLanguage()
const { publicSiteUrl } = usePublicSiteUrl()

const siteQrFontFamily = APP_REFINED_SANS_STACK

const qrSrc = computed(() => {
  const url = publicSiteUrl.value
  if (!url) {
    return ''
  }
  return `/api/qrcode?data=${encodeURIComponent(url)}&size=260`
})

function closeModal(): void {
  emit('close')
}

function handleBackdropClick(event: MouseEvent): void {
  if (event.target === event.currentTarget) {
    closeModal()
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="logo-site-qr">
      <div
        v-if="visible"
        class="logo-site-qr-overlay fixed inset-0 z-[1100] flex items-center justify-center p-4"
        @click="handleBackdropClick"
        @pointerenter="emit('hoverEnter')"
        @pointerleave="emit('hoverLeave')"
      >
        <div
          class="absolute inset-0 bg-stone-900/45 backdrop-blur-md"
          aria-hidden="true"
        />

        <div
          class="logo-site-qr-card relative w-full max-w-[480px] overflow-hidden rounded-2xl border border-stone-200/80 bg-white shadow-2xl"
          role="dialog"
          aria-modal="true"
          :aria-label="t('sidebar.logoSiteQrTitle')"
          @click.stop
        >
          <div class="flex items-center justify-between gap-3 border-b border-stone-100 px-5 py-4">
            <div class="logo-site-qr-typography flex min-w-0 flex-1 items-center gap-2.5">
              <div
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-stone-900 text-sm font-semibold leading-none text-white shadow-sm"
                aria-hidden="true"
              >
                M
              </div>
              <span
                class="truncate text-base font-semibold leading-snug tracking-tight text-stone-900 sm:text-[1.0625rem]"
              >
                {{ t('sidebar.brandTitle') }}
              </span>
            </div>
            <ElButton
              class="logo-site-qr-close -mr-1 shrink-0"
              text
              circle
              :aria-label="t('common.close')"
              @click="closeModal"
            >
              <X
                class="h-5 w-5"
                aria-hidden="true"
              />
            </ElButton>
          </div>

          <div class="logo-site-qr-body logo-site-qr-typography px-5 pb-6 pt-5">
            <p class="w-full max-w-sm px-1 text-center text-sm font-medium leading-snug tracking-tight text-slate-600">
              {{ t('sidebar.logoSiteQrHint') }}
            </p>

            <div class="logo-site-qr-stage">
              <div class="qr-ga-stack">
                <div
                  class="qr-ga-wrap logo-site-qr-aura"
                  role="img"
                  :aria-label="t('sidebar.logoSiteQrTitle')"
                >
                  <div class="logo-site-qr-inner">
                    <img
                      v-if="qrSrc && visible"
                      :src="qrSrc"
                      alt=""
                      width="260"
                      height="260"
                      class="logo-site-qr-img"
                      decoding="async"
                    />
                  </div>
                </div>
              </div>
            </div>

            <p
              v-if="publicSiteUrl"
              class="w-full max-w-sm truncate px-1 text-center text-xs font-medium text-slate-400"
            >
              {{ publicSiteUrl }}
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
@property --logo-site-qr-aura-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.logo-site-qr-typography {
  font-family: v-bind(siteQrFontFamily);
  font-feature-settings:
    'tnum' 1,
    'kern' 1;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.logo-site-qr-close {
  color: rgb(148 163 184);
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.logo-site-qr-close:hover {
  color: rgb(15 23 42);
  background: rgb(241 245 249) !important;
}

.logo-site-qr-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  text-align: center;
}

.logo-site-qr-stage {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 4px 0 0;
  min-height: 0;
  align-items: center;
}

.qr-ga-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
  width: 100%;
}

.qr-ga-wrap {
  position: relative;
  width: 300px;
  height: 300px;
  max-width: min(300px, 82vw);
  max-height: min(300px, 82vw);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 1.125rem;
  box-shadow:
    0 1px 2px rgb(15 23 42 / 0.04),
    0 12px 32px rgb(15 23 42 / 0.08);
}

.logo-site-qr-aura::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  border-radius: 1.125rem;
  padding: 4px;
  --logo-site-qr-aura-angle: 0deg;
  background: conic-gradient(
    from var(--logo-site-qr-aura-angle) at 50% 50%,
    #f1f5f9 0deg,
    #cbd5e1 45deg,
    #64748b 90deg,
    #0d9488 130deg,
    #10b981 170deg,
    #34d399 210deg,
    #059669 250deg,
    #94a3b8 295deg,
    #f8fafc 360deg
  );
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  pointer-events: none;
  animation: logo-site-qr-aura-travel 2.5s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .logo-site-qr-aura::before {
    animation: none;
    --logo-site-qr-aura-angle: 200deg;
  }
}

@keyframes logo-site-qr-aura-travel {
  to {
    --logo-site-qr-aura-angle: 360deg;
  }
}

.qr-ga-wrap > * {
  position: relative;
  z-index: 1;
}

.logo-site-qr-inner {
  position: relative;
  z-index: 1;
  padding: 12px;
  border-radius: 0.875rem;
  overflow: hidden;
  background: var(--el-bg-color, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 0.06);
}

.logo-site-qr-img {
  display: block;
  width: 260px;
  height: 260px;
  max-width: min(260px, 68vw);
  max-height: min(260px, 68vw);
  object-fit: contain;
  border-radius: 6px;
}

.logo-site-qr-enter-active,
.logo-site-qr-leave-active {
  transition: opacity 0.2s ease;
}

.logo-site-qr-enter-active .logo-site-qr-card,
.logo-site-qr-leave-active .logo-site-qr-card {
  transition:
    transform 0.22s ease,
    opacity 0.22s ease;
}

.logo-site-qr-enter-from,
.logo-site-qr-leave-to {
  opacity: 0;
}

.logo-site-qr-enter-from .logo-site-qr-card,
.logo-site-qr-leave-to .logo-site-qr-card {
  opacity: 0;
  transform: scale(0.96) translateY(6px);
}
</style>
