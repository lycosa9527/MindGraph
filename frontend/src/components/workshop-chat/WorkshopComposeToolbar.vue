<script setup lang="ts">
import { useTemplateRef } from 'vue'

import { onClickOutside } from '@vueuse/core'

import {
  Bold,
  Code,
  CodeSquare,
  Eye,
  EyeOff,
  Italic,
  Link2,
  List,
  ListOrdered,
  MessageSquareQuote,
  Paperclip,
  SendHorizonal,
  Sigma,
  Smile,
  SquareChevronDown,
  Strikethrough,
  Table,
} from '@lucide/vue'

import OneSentenceKittyAvatar from '@/components/canvas/OneSentenceKittyAvatar.vue'
import TrainingRolePicker from '@/components/training/TrainingRolePicker.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import type { ComposeFormatType } from '@/utils/workshopComposeFormat'

import EmojiPicker from './EmojiPicker.vue'
import MindGraphMarkIcon from './MindGraphMarkIcon.vue'

const props = withDefaults(
  defineProps<{
    canSend: boolean
    previewOn: boolean
    formatDisabled: boolean
    uploading: boolean
    showEmojiPicker: boolean
    showRolePicker: boolean
    showSend?: boolean
  }>(),
  { showSend: true }
)

const emit = defineEmits<{
  format: [type: ComposeFormatType]
  togglePreview: []
  upload: []
  'update:showEmojiPicker': [value: boolean]
  'update:showRolePicker': [value: boolean]
  emoji: [name: string, code: string]
  pickRole: [roleId: string]
  openDiagram: []
  send: []
}>()

const { t } = useLanguage()
const roleMenuRef = useTemplateRef<HTMLElement>('roleMenuRef')

onClickOutside(roleMenuRef, () => {
  if (props.showRolePicker) {
    emit('update:showRolePicker', false)
  }
})

const formatButtons: { key: ComposeFormatType; icon: typeof Bold; titleKey: string }[] = [
  { key: 'bold', icon: Bold, titleKey: 'workshop.bold' },
  { key: 'italic', icon: Italic, titleKey: 'workshop.italic' },
  { key: 'strikethrough', icon: Strikethrough, titleKey: 'workshop.strikethrough' },
  { key: 'link', icon: Link2, titleKey: 'workshop.insertLink' },
  { key: 'numbered', icon: ListOrdered, titleKey: 'workshop.numberedList' },
  { key: 'bulleted', icon: List, titleKey: 'workshop.bulletedList' },
  { key: 'quote', icon: MessageSquareQuote, titleKey: 'workshop.quote' },
  { key: 'spoiler', icon: SquareChevronDown, titleKey: 'workshop.spoiler' },
  { key: 'code', icon: Code, titleKey: 'workshop.code' },
  { key: 'codeBlock', icon: CodeSquare, titleKey: 'workshop.codeBlock' },
  { key: 'latex', icon: Sigma, titleKey: 'workshop.math' },
  { key: 'table', icon: Table, titleKey: 'workshop.table' },
]
</script>

<template>
  <div class="compose-toolbar">
    <div class="compose-toolbar__fmt">
      <button
        type="button"
        class="compose-toolbar__btn"
        :title="previewOn ? t('workshop.exitPreview') : t('workshop.preview')"
        @click="emit('togglePreview')"
      >
        <EyeOff
          v-if="previewOn"
          :size="15"
        />
        <Eye
          v-else
          :size="15"
        />
      </button>

      <span class="compose-toolbar__divider" />

      <button
        v-for="btn in formatButtons"
        :key="btn.key"
        type="button"
        class="compose-toolbar__btn"
        :title="t(btn.titleKey)"
        :disabled="formatDisabled"
        @click="emit('format', btn.key)"
      >
        <component
          :is="btn.icon"
          :size="15"
        />
      </button>

      <span class="compose-toolbar__divider" />

      <button
        type="button"
        class="compose-toolbar__btn"
        :class="{ 'compose-toolbar__btn--busy': uploading }"
        :title="t('workshop.uploadFile')"
        :disabled="uploading || formatDisabled"
        @click="emit('upload')"
      >
        <Paperclip :size="15" />
      </button>

      <el-popover
        :visible="showEmojiPicker"
        placement="top-end"
        :width="260"
        trigger="click"
        :show-arrow="false"
        @update:visible="emit('update:showEmojiPicker', $event)"
      >
        <template #reference>
          <button
            type="button"
            class="compose-toolbar__btn"
            :title="t('workshop.emoji')"
            :disabled="formatDisabled"
            @click="emit('update:showEmojiPicker', !props.showEmojiPicker)"
          >
            <Smile :size="15" />
          </button>
        </template>
        <EmojiPicker @select="(name, code) => emit('emoji', name, code)" />
      </el-popover>

      <div
        ref="roleMenuRef"
        class="compose-toolbar__menu"
        @click.stop
      >
        <button
          type="button"
          class="compose-toolbar__btn compose-toolbar__btn--kitty"
          :class="{ 'compose-toolbar__btn--on': showRolePicker }"
          :title="t('workshop.kitty')"
          :disabled="formatDisabled || uploading"
          @click="emit('update:showRolePicker', !props.showRolePicker)"
        >
          <OneSentenceKittyAvatar :size="20" />
        </button>
        <div
          v-if="showRolePicker"
          class="compose-toolbar__sheet"
        >
          <TrainingRolePicker
            preview-side="left"
            @pick="(roleId) => emit('pickRole', roleId)"
          />
        </div>
      </div>

      <button
        type="button"
        class="compose-toolbar__btn compose-toolbar__btn--mark"
        :title="t('workshop.diagram')"
        :disabled="formatDisabled || uploading"
        @click="emit('openDiagram')"
      >
        <MindGraphMarkIcon :size="16" />
      </button>
    </div>

    <button
      v-if="showSend"
      type="button"
      class="compose-toolbar__send"
      :disabled="!canSend"
      @click="emit('send')"
    >
      <SendHorizonal :size="16" />
    </button>
  </div>
</template>

<style scoped>
.compose-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 6px 5px;
  border-top: 1px solid hsl(0deg 0% 0% / 6%);
  overflow: visible;
}

.compose-toolbar__fmt {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 1px;
  min-width: 0;
}

.compose-toolbar__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  border-radius: 4px;
  cursor: pointer;
  color: hsl(0deg 0% 42%);
  transition: all 100ms ease;
}

.compose-toolbar__btn:hover:not(:disabled) {
  background: hsl(0deg 0% 0% / 6%);
  color: hsl(0deg 0% 15%);
}

.compose-toolbar__btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.compose-toolbar__btn--busy {
  animation: compose-toolbar-pulse 1.5s infinite;
}

.compose-toolbar__btn--mark {
  padding: 0;
}

.compose-toolbar__btn--kitty {
  padding: 0;
}

.compose-toolbar__btn--kitty :deep(.one-sentence-kitty-avatar) {
  box-shadow: none;
}

.compose-toolbar__btn--on {
  background: hsl(0deg 0% 0% / 6%);
}

.compose-toolbar__menu {
  position: relative;
}

.compose-toolbar__sheet {
  position: absolute;
  right: 0;
  bottom: calc(100% + 0.35rem);
  z-index: 40;
  overflow: visible;
  border: 1px solid hsl(0deg 0% 0% / 10%);
  background: hsl(0deg 0% 100%);
  padding: 0.55rem;
  box-shadow: 0 10px 28px rgb(28 25 23 / 0.12);
}

@keyframes compose-toolbar-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.compose-toolbar__divider {
  width: 1px;
  height: 16px;
  background: hsl(0deg 0% 0% / 10%);
  margin: 0 5px;
}

.compose-toolbar__send {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 30px;
  flex-shrink: 0;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  background: hsl(228deg 56% 58%);
  color: hsl(0deg 0% 100%);
  transition: all 120ms ease;
  box-shadow: 0 1px 2px hsl(228deg 56% 58% / 25%);
}

.compose-toolbar__send:hover:not(:disabled) {
  background: hsl(228deg 48% 48%);
  box-shadow: 0 2px 4px hsl(228deg 56% 58% / 30%);
}

.compose-toolbar__send:active:not(:disabled) {
  transform: scale(0.96);
}

.compose-toolbar__send:disabled {
  opacity: 0.35;
  cursor: default;
  box-shadow: none;
}
</style>
