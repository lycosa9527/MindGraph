<script setup lang="ts">
/**
 * Seminar share sheet: a scrollable long-image preview, then a PNG download.
 */
import { computed, ref, watch } from 'vue'

import { ElDialog } from 'element-plus'

import { Download, Star, X } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { beijingWallClock, parseApiInstant } from '@/utils/beijingClock'
import { dataUrlToBlob, deliverExportFile } from '@/utils/deliverExportFile'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

export interface SeminarShareLine {
  key: string
  role: 'user' | 'assistant'
  authorName: string
  content: string
  createdAt: string
  highlighted: boolean
}

const props = defineProps<{
  open: boolean
  title: string
  lines: SeminarShareLine[]
  memberCount: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const cardRef = ref<HTMLElement | null>(null)
const exporting = ref(false)
const qrSrc = ref('')

const exportedAt = computed(() => {
  const wall = beijingWallClock()
  return `${wall.year}-${wall.month}-${wall.day} ${wall.hour}:${wall.minute}`
})

const siteUrl = computed(() => (typeof window === 'undefined' ? '' : window.location.origin))

function formatWhen(iso: string): string {
  const date = parseApiInstant(iso)
  if (!date) {
    return ''
  }
  const wall = beijingWallClock(date)
  return `${Number(wall.month)}/${Number(wall.day)} ${wall.hour}:${wall.minute}`
}

async function loadQr(): Promise<void> {
  if (!siteUrl.value) {
    return
  }
  try {
    const response = await fetch(`/api/qrcode?data=${encodeURIComponent(siteUrl.value)}&size=160`)
    if (!response.ok) {
      return
    }
    const blob = await response.blob()
    const bytes = new Uint8Array(await blob.arrayBuffer())
    let binary = ''
    for (const byte of bytes) {
      binary += String.fromCharCode(byte)
    }
    const mime = blob.type || 'image/png'
    qrSrc.value = `data:${mime};base64,${btoa(binary)}`
  } catch {
    qrSrc.value = ''
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      void loadQr()
    }
  }
)

async function download(): Promise<void> {
  const card = cardRef.value
  if (!card || props.lines.length === 0 || exporting.value) {
    return
  }
  exporting.value = true
  try {
    const { toPng } = await import('html-to-image')
    const dataUrl = await toPng(card, {
      backgroundColor: '#ffffff',
      pixelRatio: 2,
    })
    await deliverExportFile(dataUrlToBlob(dataUrl), 'seminar-share.png')
    notify.successKey('panels.share.exportOk')
  } catch {
    notify.errorKey('panels.share.exportFail')
  } finally {
    exporting.value = false
  }
}

function close(): void {
  emit('close')
}
</script>

<template>
  <ElDialog
    :model-value="open"
    width="min(580px, 94vw)"
    append-to-body
    :show-close="false"
    :close-on-click-modal="false"
    class="mm-share-sheet mm-seminar-swiss"
    @update:model-value="(value: boolean) => !value && close()"
  >
    <template #header>
      <div class="mm-share-sheet__head">
        <h2><I18nText k="mindmate.shareSheet.title" /></h2>
        <button
          type="button"
          class="mm-share-sheet__x"
          :aria-label="t('common.close')"
          @click="close"
        >
          <X
            :size="16"
            aria-hidden="true"
          />
        </button>
      </div>
    </template>

    <div class="mm-share-sheet__scroll">
      <article
        ref="cardRef"
        class="mm-share-card"
      >
        <header class="mm-share-card__banner">
          <h3 class="mm-share-card__heading"><I18nText k="mindmate.shareSheet.heading" /></h3>
          <p
            v-if="title"
            class="mm-share-card__sub"
          >
            {{ title }}
          </p>
        </header>
        <dl class="mm-share-card__meta">
          <div>
            <dt><I18nText k="mindmate.shareSheet.exportedAt" /></dt>
            <dd>{{ exportedAt }}</dd>
          </div>
          <div>
            <dt><I18nText k="mindmate.shareSheet.members" /></dt>
            <dd>
              <I18nText
                k="mindmate.shareSheet.memberCount"
                :params="{ n: memberCount }"
              />
            </dd>
          </div>
          <div>
            <dt><I18nText k="mindmate.shareSheet.messages" /></dt>
            <dd>
              <I18nText
                k="mindmate.shareSheet.messageCount"
                :params="{ n: lines.length }"
              />
            </dd>
          </div>
        </dl>
        <ul class="mm-share-card__list">
          <li
            v-for="line in lines"
            :key="line.key"
            class="mm-share-card__line"
          >
            <span
              class="mm-share-card__avatar"
              :style="{
                background: seminarAvatarTone(line.authorName).background,
                color: seminarAvatarTone(line.authorName).color,
              }"
              aria-hidden="true"
            >
              {{ seminarAvatarSurname(line.authorName) }}
            </span>
            <div class="mm-share-card__body">
              <p class="mm-share-card__who">
                <span>{{ line.authorName }}</span>
                <time v-if="formatWhen(line.createdAt)">{{ formatWhen(line.createdAt) }}</time>
              </p>
              <p class="mm-share-card__bubble">{{ line.content }}</p>
              <p
                v-if="line.highlighted"
                class="mm-share-card__star"
              >
                <Star
                  :size="12"
                  fill="currentColor"
                  aria-hidden="true"
                />
                <I18nText k="mindmate.shareSheet.highlighted" />
              </p>
            </div>
          </li>
        </ul>
        <footer class="mm-share-card__foot">
          <div class="mm-share-card__qr">
            <img
              v-if="qrSrc"
              :src="qrSrc"
              alt=""
            />
            <span v-else><I18nText k="mindmate.shareSheet.qrLabel" /></span>
          </div>
          <div class="mm-share-card__qr-copy">
            <p class="mm-share-card__qr-title"><I18nText k="mindmate.shareSheet.qrHint" /></p>
            <p class="mm-share-card__qr-brand"><I18nText k="mindmate.shareSheet.platform" /></p>
          </div>
        </footer>
      </article>
    </div>

    <template #footer>
      <div class="mm-share-sheet__actions">
        <button
          type="button"
          class="mm-share-sheet__cancel"
          @click="close"
        >
          <I18nText k="mindmate.shareSheet.cancel" />
        </button>
        <button
          type="button"
          class="mm-share-sheet__download"
          :disabled="exporting || lines.length === 0"
          @click="download"
        >
          <Download
            :size="15"
            aria-hidden="true"
          />
          <I18nText k="mindmate.shareSheet.download" />
        </button>
      </div>
    </template>
  </ElDialog>
</template>

<style>
.mm-share-sheet.el-dialog {
  border-radius: 12px;
  overflow: hidden;
  padding: 0;
}

.mm-share-sheet .el-dialog__header {
  margin: 0;
  padding: 0;
}

.mm-share-sheet .el-dialog__body {
  padding: 0;
  background: #f5f5f4;
}

.mm-share-sheet .el-dialog__footer {
  padding: 12px 16px 16px;
  border-top: 1px solid #f5f5f4;
  background: #fff;
}

.mm-share-sheet__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #fff;
}

.mm-share-sheet__head h2 {
  margin: 0;
  color: #1c1917;
  font-size: 16px;
  font-weight: 600;
}

.mm-share-sheet__x {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 999px;
  background: #f5f5f4;
  color: #78716c;
  cursor: pointer;
}

.mm-share-sheet__x:hover {
  background: #e7e5e4;
  color: #1c1917;
}

.mm-share-sheet__scroll {
  max-height: min(64vh, 680px);
  overflow-y: scroll;
  padding: 16px;
  background: #f5f5f4;
  scrollbar-width: thin;
  scrollbar-color: #d6d3d1 transparent;
}

.mm-share-sheet__scroll::-webkit-scrollbar {
  width: 8px;
}

.mm-share-sheet__scroll::-webkit-scrollbar-thumb {
  border-radius: 8px;
  background: #d6d3d1;
}

.mm-share-card {
  overflow: hidden;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(24, 25, 28, 0.06);
}

.mm-share-card__banner {
  padding: 18px 16px 14px;
  background: linear-gradient(180deg, #5b4fe8 0%, #6d5efc 100%);
  color: #fff;
}

.mm-share-card__heading,
.mm-share-card__sub {
  margin: 0;
}

.mm-share-card__heading {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.3;
}

.mm-share-card__sub {
  margin-top: 6px;
  font-size: 13px;
  opacity: 0.92;
}

.mm-share-card__meta {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 0.8fr;
  gap: 8px;
  margin: 0;
  padding: 12px 16px;
  background: #f3f0ff;
}

.mm-share-card__meta div {
  min-width: 0;
}

.mm-share-card__meta dt {
  color: #8b85d9;
  font-size: 11px;
}

.mm-share-card__meta dd {
  margin: 2px 0 0;
  color: #18191c;
  font-size: 13px;
  font-weight: 700;
}

.mm-share-card__list {
  list-style: none;
  margin: 0;
  padding: 14px 14px 6px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mm-share-card__line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.mm-share-card__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 13px;
  font-weight: 700;
}

.mm-share-card__body {
  min-width: 0;
  flex: 1 1 auto;
}

.mm-share-card__who {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0 0 4px;
  color: #18191c;
  font-size: 13px;
  font-weight: 700;
}

.mm-share-card__who time {
  color: #9c9aa8;
  font-size: 11px;
  font-weight: 500;
}

.mm-share-card__bubble {
  margin: 0;
  padding: 8px 10px;
  border-radius: 10px;
  background: #f4f4f6;
  color: #18191c;
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.mm-share-card__star {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 6px 0 0;
  color: #f59e0b;
  font-size: 12px;
  font-weight: 600;
}

.mm-share-card__foot {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px 16px;
  border-top: 1px solid #eeeef2;
}

.mm-share-card__qr {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 84px;
  height: 84px;
  border-radius: 8px;
  background: #f4f4f6;
  color: #9c9aa8;
  font-size: 11px;
  text-align: center;
}

.mm-share-card__qr img {
  width: 76px;
  height: 76px;
  object-fit: contain;
}

.mm-share-card__qr-copy {
  min-width: 0;
}

.mm-share-card__qr-title,
.mm-share-card__qr-brand {
  margin: 0;
}

.mm-share-card__qr-title {
  color: #18191c;
  font-size: 14px;
  font-weight: 700;
}

.mm-share-card__qr-brand {
  margin-top: 6px;
  color: #9c9aa8;
  font-size: 11px;
}

.mm-share-sheet__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.mm-share-sheet__cancel,
.mm-share-sheet__download {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  /* button:has(.i18n-label) sets height:auto and outranks a plain height. */
  min-height: 36px;
  padding: 6px 16px;
  border: 1px solid transparent;
  border-radius: 9999px;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
  cursor: pointer;
}

.mm-share-sheet__cancel {
  background: #f5f5f4;
  border-color: #e7e5e4;
  color: #44403c;
}

.mm-share-sheet__cancel:hover {
  background: #e7e5e4;
  color: #1c1917;
}

.mm-share-sheet__download {
  background: #1c1917;
  border-color: #1c1917;
  color: #fafaf9;
}

.mm-share-sheet__download:hover:not(:disabled) {
  background: #292524;
  border-color: #292524;
}

.mm-share-sheet__download:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
