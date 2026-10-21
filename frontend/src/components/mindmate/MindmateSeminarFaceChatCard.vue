<script setup lang="ts">
/**
 * Intro card for seminar face-to-face notes. Recording starts only after the button.
 */
import { ElDialog } from 'element-plus'

import heroUrl from '@/assets/seminar/face-chat-hero.jpg'
import { useLanguage } from '@/composables'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'start'): void
}>()

const { t } = useLanguage()
</script>

<template>
  <ElDialog
    :model-value="open"
    width="min(420px, 92vw)"
    align-center
    append-to-body
    class="mm-face-chat-dialog"
    @close="emit('close')"
  >
    <div class="mm-face-chat">
      <h2 class="mm-face-chat__title">
        {{ t('mindmate.faceChat.title') }}
      </h2>
      <p class="mm-face-chat__line">
        {{ t('mindmate.faceChat.subtitle') }}
      </p>
      <p class="mm-face-chat__line">
        {{ t('mindmate.faceChat.scenes') }}
      </p>
      <img
        class="mm-face-chat__hero"
        :src="heroUrl"
        alt=""
      />
      <button
        type="button"
        class="mm-face-chat__start"
        @click="emit('start')"
      >
        {{ t('mindmate.faceChat.start') }}
      </button>
    </div>
  </ElDialog>
</template>

<style>
.mm-face-chat-dialog.el-dialog {
  border-radius: 20px;
  padding: 8px 8px 28px;
}

.mm-face-chat-dialog .el-dialog__header {
  padding-bottom: 0;
}

.mm-face-chat-dialog .el-dialog__body {
  padding: 4px 28px 8px;
}

.mm-face-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.mm-face-chat__title {
  margin: 8px 0 14px;
  font-size: 22px;
  line-height: 1.35;
  font-weight: 700;
  color: #111827;
}

.mm-face-chat__line {
  margin: 0;
  color: #9aa0a8;
  font-size: 14px;
  line-height: 1.7;
}

.mm-face-chat__hero {
  width: min(100%, 320px);
  height: auto;
  margin: 8px 0 22px;
  display: block;
}

.mm-face-chat__start {
  min-width: 168px;
  height: 44px;
  padding: 0 28px;
  border: none;
  border-radius: 10px;
  background: #6d5efc;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

.mm-face-chat__start:hover {
  background: #5b4fe0;
}
</style>
