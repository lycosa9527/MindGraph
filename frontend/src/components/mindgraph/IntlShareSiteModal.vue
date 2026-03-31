<script setup lang="ts">
/**
 * Share-site modal — QR + URL for sharing the MindGraph link.
 */
import { computed } from 'vue'

import { ElButton, ElDialog } from 'element-plus'

import { X } from 'lucide-vue-next'

import { useLanguage } from '@/composables'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const { t } = useLanguage()

const siteUrl = computed(() => {
  if (typeof window === 'undefined') {
    return ''
  }
  return `${window.location.origin}/mindgraph`
})

const qrSrc = computed(() => {
  const u = siteUrl.value
  if (!u) {
    return ''
  }
  return `/api/qrcode?data=${encodeURIComponent(u)}&size=280`
})

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

function close() {
  visible.value = false
}
</script>

<template>
  <ElDialog
    v-model="visible"
    :show-close="false"
    width="440px"
    class="intl-share-site-dialog"
    align-center
    append-to-body
  >
    <template #header>
      <div class="intl-share-site-header">
        <div class="intl-share-site-header-center">
          <span class="intl-share-site-kicker">MindGraph</span>
          <h2 class="intl-share-site-title">
            {{ t('landing.international.shareSiteModalTitle') }}
          </h2>
        </div>
        <ElButton
          class="intl-share-site-close"
          text
          circle
          :aria-label="t('common.close')"
          @click="close"
        >
          <X
            class="w-5 h-5"
            aria-hidden="true"
          />
        </ElButton>
      </div>
    </template>

    <div class="intl-share-site-body">
      <div class="intl-share-site-qr-stage">
        <div
          class="intl-share-site-qr-ring"
          role="img"
          :aria-label="t('landing.international.shareSiteModalHint')"
        >
          <div class="intl-share-site-qr-inner">
            <img
              v-if="qrSrc && visible"
              :src="qrSrc"
              alt=""
              width="280"
              height="280"
              class="intl-share-site-qr-img"
              decoding="async"
            />
          </div>
        </div>
      </div>
      <p class="intl-share-site-hint">{{ t('landing.international.shareSiteModalHint') }}</p>
      <div class="intl-share-site-url-shell">
        <code class="intl-share-site-url">{{ siteUrl }}</code>
      </div>
    </div>
  </ElDialog>
</template>

<style scoped>
.intl-share-site-header {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  min-height: 48px;
  padding: 0 48px 0 8px;
}

.intl-share-site-header-center {
  text-align: center;
  max-width: 100%;
}

.intl-share-site-kicker {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgb(100 116 139);
  margin-bottom: 10px;
}

.intl-share-site-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.2;
  color: rgb(15 23 42);
}

.intl-share-site-close {
  position: absolute;
  top: -2px;
  right: -4px;
  color: rgb(148 163 184);
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.intl-share-site-close:hover {
  color: rgb(15 23 42);
  background: rgb(241 245 249) !important;
}

.intl-share-site-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 22px;
  text-align: center;
}

.intl-share-site-qr-stage {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.intl-share-site-qr-ring {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 20px;
  border: 1px solid rgb(226 232 240);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
}

.intl-share-site-qr-inner {
  position: relative;
  padding: 14px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--el-bg-color, #fff);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.intl-share-site-qr-img {
  display: block;
  width: 280px;
  height: 280px;
  max-width: min(280px, 70vw);
  max-height: min(280px, 70vw);
  object-fit: contain;
  border-radius: 4px;
}

.intl-share-site-hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: rgb(71 85 105);
  max-width: 34em;
  letter-spacing: 0.01em;
}

.intl-share-site-url-shell {
  width: 100%;
  padding: 3px;
  border-radius: 12px;
  background: linear-gradient(
    135deg,
    rgb(226 232 240) 0%,
    rgb(241 245 249) 50%,
    rgb(226 232 240) 100%
  );
  box-shadow: inset 0 1px 2px rgb(255 255 255 / 0.8);
}

.intl-share-site-url {
  display: block;
  width: 100%;
  box-sizing: border-box;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New',
    monospace;
  font-size: 12px;
  line-height: 1.55;
  word-break: break-all;
  padding: 14px 16px;
  background: rgb(255 255 255);
  border-radius: 9px;
  border: 1px solid rgb(241 245 249);
  color: rgb(51 65 85);
  text-align: center;
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.04);
}
</style>

<style>
.intl-share-site-dialog.el-dialog {
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgb(226 232 240);
  background: rgb(255 255 255);
  box-shadow:
    0 25px 50px -12px rgb(15 23 42 / 0.2),
    0 0 0 1px rgb(15 23 42 / 0.04),
    inset 0 1px 0 rgb(255 255 255 / 0.9);
}

.intl-share-site-dialog .el-dialog__header {
  padding: 20px 22px 16px;
  margin: 0;
  background: linear-gradient(180deg, rgb(252 252 254) 0%, rgb(255 255 255) 55%);
  border-bottom: 1px solid rgb(241 245 249);
}

.intl-share-site-dialog .el-dialog__body {
  padding: 26px 26px 28px;
  background: linear-gradient(
    180deg,
    rgb(255 255 255) 0%,
    rgb(248 250 252) 55%,
    rgb(252 252 254) 100%
  );
}
</style>
