<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import { useMarkdown } from '@/composables/useMarkdown'
import {
  useWorkshopChatStore,
  type ChatMessage,
  type FileAttachment,
  type ReactionGroup,
} from '@/stores/workshopChat'
import { workshopChatHrefFromState } from '@/utils/workshopChatRoute'

import FilePreview from './FilePreview.vue'
import MessageActionBar from './MessageActionBar.vue'
import MessageReactions from './MessageReactions.vue'

const { t } = useLanguage()
const { render } = useMarkdown()
const workshopStore = useWorkshopChatStore()

const CONDENSE_THRESHOLD = 300

const props = defineProps<{
  message: ChatMessage
  isOwn: boolean
  hideHeader: boolean
  reactions: ReactionGroup[]
  isStarred: boolean
  attachments: FileAttachment[]
  isUnread?: boolean
}>()

const emit = defineEmits<{
  edit: [message: ChatMessage]
  delete: [messageId: number]
  toggleReaction: [messageId: number, emojiName: string, emojiCode: string]
  toggleStar: [messageId: number]
  quote: [message: ChatMessage]
}>()

const contentRef = ref<HTMLDivElement>()
const isCondensed = ref(false)
const canCondense = ref(false)

const formattedTime = computed(() => {
  const d = new Date(props.message.created_at)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})

const isEdited = computed(() => !!props.message.edited_at)

const renderedContent = computed(() => {
  if (props.message.is_deleted) return ''
  return render(props.message.content)
})

const senderInitial = computed(() => {
  if (props.message.sender_avatar) return props.message.sender_avatar
  return (props.message.sender_name || '?')[0].toUpperCase()
})

onMounted(() => {
  nextTick(() => {
    if (contentRef.value) {
      const height = contentRef.value.scrollHeight
      if (height > CONDENSE_THRESHOLD) {
        canCondense.value = true
        isCondensed.value = true
      }
    }
  })
})

function handleToggleCondense(): void {
  isCondensed.value = !isCondensed.value
}

function handleCopyLink(): void {
  const id = props.message.id
  const hasWorkshopNarrow =
    workshopStore.currentDMPartnerId != null ||
    workshopStore.showChannelBrowser ||
    workshopStore.currentChannelId != null
  const url = hasWorkshopNarrow
    ? `${window.location.origin}${workshopChatHrefFromState({
        currentChannelId: workshopStore.currentChannelId,
        currentTopicId: workshopStore.currentTopicId,
        currentDMPartnerId: workshopStore.currentDMPartnerId,
        showChannelBrowser: workshopStore.showChannelBrowser,
        workshopHomeViewActive: workshopStore.workshopHomeViewActive,
        mainChannelFeedActive: workshopStore.mainChannelFeedActive,
        focusMessageId: id,
      })}`
    : `${window.location.origin}${window.location.pathname}${window.location.search}#msg-${id}`
  navigator.clipboard.writeText(url)
}

function handleAddReaction(emojiName: string, emojiCode: string): void {
  emit('toggleReaction', props.message.id, emojiName, emojiCode)
}
</script>

<template>
  <div
    :id="`msg-${message.id}`"
    class="msg-row"
    :class="{
      'msg-row--with-sender': !hideHeader,
      'msg-row--continuation': hideHeader,
    }"
  >
    <!-- Unread marker (Zulip-style 2px left bar) -->
    <div
      v-if="isUnread"
      class="msg-unread-marker"
    />

    <!-- Hover action bar -->
    <div v-if="!message.is_deleted" class="msg-row__actions">
      <MessageActionBar
        :is-own="isOwn"
        :is-starred="isStarred"
        :is-condensed="isCondensed"
        @add-reaction="handleAddReaction"
        @toggle-star="emit('toggleStar', message.id)"
        @quote="emit('quote', message)"
        @copy-link="handleCopyLink"
        @edit="emit('edit', message)"
        @delete="emit('delete', message.id)"
        @toggle-condense="handleToggleCondense"
      />
    </div>

    <!-- Zulip-style message grid -->
    <div class="msg-box">
      <!-- Avatar column -->
      <div v-if="!hideHeader" class="msg-box__avatar">
        <div class="msg-avatar">{{ senderInitial }}</div>
      </div>
      <!-- Empty avatar gutter for continuation messages -->
      <div v-else class="msg-box__time-gutter">
        <span class="msg-time-inline">{{ formattedTime }}</span>
      </div>

      <!-- Sender + time header row -->
      <div v-if="!hideHeader" class="msg-box__sender">
        <span class="msg-sender-name">{{ message.sender_name }}</span>
      </div>
      <div v-if="!hideHeader" class="msg-box__time">
        <span class="msg-timestamp">{{ formattedTime }}</span>
        <span v-if="isEdited" class="msg-edited">{{ t('workshop.edited') }}</span>
        <span v-if="isStarred" class="msg-star" :title="t('workshop.starMessage')">★</span>
      </div>

      <!-- Content area spans across sender+time columns -->
      <div
        class="msg-box__content"
        :class="{ 'msg-box__content--no-header': hideHeader }"
      >
        <!-- Body -->
        <div v-if="!message.is_deleted">
          <div
            ref="contentRef"
            class="msg-content"
            :class="{ 'msg-content--condensed': isCondensed }"
            v-html="renderedContent"
          />
          <button
            v-if="canCondense"
            class="msg-condense-toggle"
            @click="handleToggleCondense"
          >
            {{ isCondensed ? t('workshop.showMore') : t('workshop.showLess') }}
          </button>
        </div>
        <div v-else class="msg-deleted">
          {{ t('workshop.messageDeleted') }}
        </div>

        <!-- Attachments -->
        <FilePreview
          v-if="attachments.length > 0"
          :attachments="attachments"
        />

        <!-- Reactions -->
        <MessageReactions
          v-if="reactions.length > 0"
          :reactions="reactions"
          :message-id="message.id"
          @toggle="(msgId, name, code) => emit('toggleReaction', msgId, name, code)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---------- Message row ---------- */
.msg-row {
  position: relative;
  padding: 1px 0;
  transition: background-color 100ms ease;
}

.msg-row:hover {
  background: hsl(210deg 20% 97%);
}

.msg-row--with-sender {
  margin-top: 10px;
}

.msg-row--continuation {
  margin-top: 0;
}

/* ---------- Unread marker ---------- */
.msg-unread-marker {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: hsl(217deg 64% 59%);
  border-radius: 0 2px 2px 0;
}

/* ---------- Action bar ---------- */
.msg-row__actions {
  position: absolute;
  top: -10px;
  right: 10px;
  z-index: 5;
  opacity: 0;
  transform: translateY(2px);
  transition: opacity 100ms ease, transform 100ms ease;
}

.msg-row:hover .msg-row__actions {
  opacity: 1;
  transform: translateY(0);
}

/* ---------- Message grid (Zulip-style) ---------- */
.msg-box {
  display: grid;
  grid-template-columns: 40px 1fr auto;
  grid-template-rows: auto 1fr;
  column-gap: 8px;
  padding: 3px 14px;
}

/* Avatar */
.msg-box__avatar {
  grid-row: 1 / 3;
  grid-column: 1;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 2px;
}

.msg-avatar {
  width: 35px;
  height: 35px;
  border-radius: 5px;
  background: hsl(214deg 32% 86%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: hsl(214deg 40% 36%);
  flex-shrink: 0;
  user-select: none;
}

/* Inline time for continuation messages */
.msg-box__time-gutter {
  grid-row: 1 / 3;
  grid-column: 1;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 2px;
}

.msg-time-inline {
  font-size: 10px;
  color: transparent;
  width: 35px;
  text-align: center;
  line-height: 22px;
  transition: color 100ms ease;
  font-variant-numeric: tabular-nums;
}

.msg-row:hover .msg-time-inline {
  color: hsl(0deg 0% 52%);
}

/* Sender name */
.msg-box__sender {
  grid-row: 1;
  grid-column: 2;
  display: flex;
  align-items: baseline;
}

.msg-sender-name {
  font-size: 14px;
  font-weight: 700;
  color: hsl(210deg 36% 22%);
  cursor: pointer;
  line-height: 20px;
}

.msg-sender-name:hover {
  text-decoration: underline;
}

/* Timestamp + edited + star */
.msg-box__time {
  grid-row: 1;
  grid-column: 3;
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.msg-timestamp {
  font-size: 11px;
  color: hsl(0deg 0% 52%);
  font-variant-numeric: tabular-nums;
  line-height: 20px;
}

.msg-edited {
  font-size: 10px;
  color: hsl(0deg 0% 55%);
  font-style: italic;
  padding: 1px 5px;
  background: hsl(0deg 0% 0% / 4%);
  border-radius: 3px;
}

.msg-star {
  font-size: 13px;
  color: hsl(45deg 92% 50%);
}

/* Content */
.msg-box__content {
  grid-row: 2;
  grid-column: 2 / 4;
  min-width: 0;
}

.msg-box__content--no-header {
  grid-row: 1 / 3;
}

/* ---------- Message body ---------- */
.msg-content {
  font-size: 14px;
  line-height: 1.55;
  color: hsl(0deg 0% 18%);
  word-break: break-word;
  overflow-wrap: break-word;
}

.msg-content--condensed {
  max-height: 300px;
  overflow: hidden;
  mask-image: linear-gradient(to bottom, black 85%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, black 85%, transparent 100%);
}

/* Prose overrides */
.msg-content :deep(p) { margin: 0 0 4px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }

.msg-content :deep(pre) {
  margin: 8px 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: hsl(220deg 14% 14%);
  color: hsl(0deg 0% 88%);
  font-size: 13px;
  line-height: 1.45;
  overflow-x: auto;
  border: 1px solid hsl(220deg 10% 20%);
}

.msg-content :deep(code) {
  padding: 1.5px 5px;
  border-radius: 3px;
  background: hsl(228deg 20% 95%);
  color: hsl(228deg 50% 42%);
  font-size: 12.5px;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
}

.msg-content :deep(pre code) {
  padding: 0;
  background: none;
  color: inherit;
  font-size: inherit;
  border: none;
}

.msg-content :deep(a) {
  color: hsl(228deg 56% 52%);
  text-decoration: none;
  font-weight: 500;
}

.msg-content :deep(a:hover) { text-decoration: underline; }

.msg-content :deep(blockquote) {
  margin: 6px 0;
  padding: 6px 12px;
  border-left: 3px solid hsl(228deg 40% 76%);
  color: hsl(0deg 0% 36%);
  background: hsl(228deg 20% 97%);
  border-radius: 0 4px 4px 0;
}

.msg-content :deep(ul),
.msg-content :deep(ol) {
  margin: 4px 0;
  padding-left: 22px;
}

.msg-content :deep(li) { margin-bottom: 2px; }

.msg-content :deep(img) {
  max-width: 100%;
  max-height: 320px;
  border-radius: 6px;
  margin: 6px 0;
  border: 1px solid hsl(0deg 0% 0% / 8%);
}

.msg-content :deep(table) {
  border-collapse: collapse;
  margin: 6px 0;
  font-size: 13px;
}

.msg-content :deep(th),
.msg-content :deep(td) {
  border: 1px solid hsl(0deg 0% 0% / 12%);
  padding: 4px 10px;
}

.msg-content :deep(th) {
  background: hsl(0deg 0% 96%);
  font-weight: 600;
}

.msg-content :deep(hr) {
  border: none;
  border-top: 1px solid hsl(0deg 0% 0% / 10%);
  margin: 8px 0;
}

/* Condense toggle */
.msg-condense-toggle {
  font-size: 12px;
  color: hsl(228deg 56% 52%);
  background: none;
  border: none;
  cursor: pointer;
  padding: 3px 0;
  margin-top: 2px;
  font-weight: 500;
}

.msg-condense-toggle:hover { text-decoration: underline; }

/* Deleted */
.msg-deleted {
  font-size: 13px;
  color: hsl(0deg 0% 52%);
  font-style: italic;
  padding: 2px 0;
}
</style>
