<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import type { ChatMessage } from '@/stores/workshopChat'

import ChatMessageItem from './ChatMessageItem.vue'
import RecipientBar from './RecipientBar.vue'

const props = defineProps<{
  messages: ChatMessage[]
  loading?: boolean
  channelName?: string
  channelType?: 'announce' | 'public' | 'private'
  channelColor?: string
  topicName?: string
  dmPartnerName?: string
}>()

const emit = defineEmits<{
  loadMore: []
  backToTopicList: []
  editMessage: [message: ChatMessage]
  deleteMessage: [messageId: number]
  quote: [message: ChatMessage]
}>()

const { t } = useLanguage()
const authStore = useAuthStore()
const store = useWorkshopChatStore()
const containerRef = ref<HTMLDivElement>()
const isAtBottom = ref(true)

interface MessageGroup {
  type: 'date-divider' | 'recipient-group'
  dateLabel?: string
  messages?: ChatMessage[]
}

const groupedMessages = computed<MessageGroup[]>(() => {
  if (props.messages.length === 0) return []

  const groups: MessageGroup[] = []
  let currentDateStr = ''
  let currentBatch: ChatMessage[] = []

  function flushBatch(): void {
    if (currentBatch.length > 0) {
      groups.push({ type: 'recipient-group', messages: [...currentBatch] })
      currentBatch = []
    }
  }

  for (const msg of props.messages) {
    const msgDate = new Date(msg.created_at)
    const dateStr = msgDate.toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: msgDate.getFullYear() !== new Date().getFullYear()
        ? 'numeric'
        : undefined,
    })

    if (dateStr !== currentDateStr) {
      flushBatch()
      currentDateStr = dateStr
      groups.push({ type: 'date-divider', dateLabel: dateStr })
    }

    currentBatch.push(msg)
  }

  flushBatch()
  return groups
})

function shouldHideHeader(messages: ChatMessage[], index: number): boolean {
  if (index === 0) return false
  const prev = messages[index - 1]
  const curr = messages[index]
  if (prev.sender_id !== curr.sender_id) return false
  const prevTime = new Date(prev.created_at).getTime()
  const currTime = new Date(curr.created_at).getTime()
  return currTime - prevTime < 5 * 60 * 1000
}

function scrollToBottom(): void {
  nextTick(() => {
    if (containerRef.value) {
      containerRef.value.scrollTop = containerRef.value.scrollHeight
    }
  })
}

function scrollToMessageId(messageId: number): void {
  nextTick(() => {
    requestAnimationFrame(() => {
      const root = containerRef.value
      if (!root) {
        return
      }
      const el = root.querySelector(`#msg-${messageId}`)
      if (!(el instanceof HTMLElement)) {
        return
      }
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('msg-row--search-focus')
      window.setTimeout(() => {
        el.classList.remove('msg-row--search-focus')
      }, 2400)
    })
  })
}

function handleScroll(): void {
  if (!containerRef.value) return
  const el = containerRef.value
  isAtBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 50
  if (el.scrollTop < 100 && !props.loading) {
    emit('loadMore')
  }
}

watch(
  () => props.messages.length,
  () => {
    if (isAtBottom.value) scrollToBottom()
  },
)

watch(
  () => props.messages,
  (msgs) => {
    if (msgs.length > 0) {
      const ids = msgs.map(m => m.id)
      store.fetchReactionsBatch(ids)
      store.fetchStarredBatch(ids)
      store.fetchAttachmentsBatch(ids)
    }
  },
  { immediate: true },
)

onMounted(scrollToBottom)

defineExpose({ scrollToBottom, scrollToMessageId })
</script>

<template>
  <div
    ref="containerRef"
    class="msg-feed"
    @scroll="handleScroll"
  >
    <!-- Loading spinner -->
    <div v-if="loading" class="msg-feed__loading">
      <div class="msg-feed__spinner" />
    </div>

    <!-- Empty state -->
    <div v-if="!loading && messages.length === 0" class="msg-feed__empty">
      <p>{{ t('workshop.noMessagesYet') }}</p>
      <p class="msg-feed__empty-hint">{{ t('workshop.startConversation') }}</p>
    </div>

    <!-- Groups -->
    <template v-for="(group, gi) in groupedMessages" :key="gi">
      <!-- Date divider -->
      <div v-if="group.type === 'date-divider'" class="msg-date-divider">
        <span class="msg-date-divider__label">{{ group.dateLabel }}</span>
      </div>

      <!-- Recipient group: sticky bar + continuous messages -->
      <div v-if="group.type === 'recipient-group' && group.messages" class="msg-recipient-group">
        <RecipientBar
          v-if="channelName || dmPartnerName"
          :type="dmPartnerName ? 'dm' : 'channel'"
          :channel-name="channelName"
          :channel-type="channelType"
          :channel-color="channelColor"
          :topic-name="topicName"
          :dm-partner-name="dmPartnerName"
          :enable-channel-navigate="Boolean(topicName && channelName && !dmPartnerName)"
          :is-sticky="true"
          @channel-navigate="emit('backToTopicList')"
        >
          <template v-if="$slots.recipientActions" #actions>
            <slot name="recipientActions" />
          </template>
        </RecipientBar>

        <div class="msg-recipient-group__body">
          <ChatMessageItem
            v-for="(msg, idx) in group.messages"
            :key="msg.id"
            :message="msg"
            :is-own="String(msg.sender_id) === authStore.user?.id"
            :hide-header="shouldHideHeader(group.messages!, idx)"
            :reactions="store.getReactionsForMessage(msg.id)"
            :is-starred="store.isMessageStarred(msg.id)"
            :attachments="store.getAttachmentsForMessage(msg.id)"
            @edit="emit('editMessage', $event)"
            @delete="emit('deleteMessage', $event)"
            @toggle-reaction="(msgId, name, code) => store.toggleReaction(msgId, name, code)"
            @toggle-star="(msgId) => store.toggleStar(msgId)"
            @quote="emit('quote', $event)"
          />
        </div>
      </div>
    </template>

    <div class="msg-feed__bottom-pad" />
  </div>
</template>

<style scoped>
.msg-feed {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0;
  background: hsl(0deg 0% 97%);
}

.msg-feed::-webkit-scrollbar { width: 6px; }

.msg-feed::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 3px;
}

.msg-feed:hover::-webkit-scrollbar-thumb {
  background: hsl(0deg 0% 0% / 14%);
}

/* Loading */
.msg-feed__loading {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.msg-feed__spinner {
  width: 22px;
  height: 22px;
  border: 2px solid hsl(0deg 0% 84%);
  border-top-color: hsl(228deg 56% 58%);
  border-radius: 50%;
  animation: msg-spin 0.65s linear infinite;
}

@keyframes msg-spin {
  to { transform: rotate(360deg); }
}

/* Empty */
.msg-feed__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: hsl(0deg 0% 55%);
  font-size: 14px;
  gap: 4px;
}

.msg-feed__empty-hint {
  font-size: 12px;
  color: hsl(0deg 0% 62%);
}

/* Date divider — Zulip-style: centered label on thin line */
.msg-date-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  margin: 8px 14px;
}

.msg-date-divider::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: hsl(0deg 0% 0% / 8%);
}

.msg-date-divider__label {
  position: relative;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: hsl(0deg 0% 15% / 50%);
  white-space: nowrap;
  padding: 2px 10px;
  background: hsl(0deg 0% 97%);
  border-radius: 10px;
}

/* Recipient group — continuous flow, no card boxing */
.msg-recipient-group {
  margin-bottom: 0;
}

.msg-recipient-group__body {
  background: hsl(0deg 0% 100%);
  border-left: 1px solid hsl(0deg 0% 0% / 8%);
  border-right: 1px solid hsl(0deg 0% 0% / 8%);
  border-bottom: 1px solid hsl(0deg 0% 0% / 8%);
  padding: 4px 0 6px;
}

.msg-feed__bottom-pad { height: 24px; }
</style>
