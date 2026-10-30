<script setup lang="ts">
/**
 * Intro card for seminar face-to-face notes. Recording starts only after the button.
 */
import { ElDialog } from 'element-plus'

import heroUrl from '@/assets/seminar/face-chat-hero.jpg'

defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'start'): void
}>()
</script>

<template>
  <ElDialog
    :model-value="open"
    width="min(420px, 92vw)"
    align-center
    append-to-body
    class="mm-face-chat-dialog mm-seminar-swiss"
    @close="emit('close')"
  >
    <div class="mm-face-chat">
      <h2 class="mm-face-chat__title">
        <I18nText k="mindmate.faceChat.title" />
      </h2>
      <p class="mm-face-chat__line">
        <I18nText k="mindmate.faceChat.subtitle" />
      </p>
      <p class="mm-face-chat__line">
        <I18nText k="mindmate.faceChat.scenes" />
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
        <I18nText k="mindmate.faceChat.start" />
      </button>
    </div>
  </ElDialog>
</template>

<style>
.mm-face-chat-dialog.el-dialog {
  border-radius: 12px;
  padding: 0 0 8px;
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
  font-weight: 600;
  color: #1c1917;
}

.mm-face-chat__line {
  margin: 0;
  color: #78716c;
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
  min-height: 36px;
  padding: 8px 20px;
  border: 1px solid #1c1917;
  border-radius: 9999px;
  background: #1c1917;
  color: #fafaf9;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.2;
  cursor: pointer;
}

.mm-face-chat__start:hover {
  background: #292524;
  border-color: #292524;
}
</style>
