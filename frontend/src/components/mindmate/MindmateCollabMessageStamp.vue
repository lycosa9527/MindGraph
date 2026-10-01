<script setup lang="ts">
/**
 * Time stamp and WhatsApp-style read marks for one seminar line.
 * Hover or focus on the checks lists who has read it.
 */
import { computed, ref } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'
import {
  type CollabReadCursor,
  type CollabReceipt,
  collabReceiptState,
  formatCollabMessageStamp,
  readersForCollabMessage,
} from '@/utils/mindmateCollabRead'

const props = defineProps<{
  messageId?: number
  createdAt?: string
  senderUserId?: number | null
  isOwn: boolean
  readCursors?: readonly CollabReadCursor[]
}>()

const { t } = useLanguage()
const open = ref(false)

const readers = computed(() =>
  readersForCollabMessage(props.readCursors ?? [], props.messageId, props.senderUserId)
)

const receipt = computed<CollabReceipt>(() =>
  collabReceiptState(props.messageId, readers.value.length)
)

const stamp = computed(() => formatCollabMessageStamp(props.createdAt))

const markLabel = computed(() => {
  if (receipt.value === 'sending') {
    return t('mindmate.collabSending')
  }
  if (readers.value.length === 0) {
    return t('mindmate.collabReadNone')
  }
  return `${t('mindmate.collabReadBy')}: ${readers.value.map((row) => row.username).join(', ')}`
})

function showReaders(): void {
  open.value = true
}

function hideReaders(): void {
  open.value = false
}
</script>

<template>
  <div
    v-if="stamp || isOwn"
    class="mindmate-collab-stamp"
    :class="{ 'mindmate-collab-stamp--own': isOwn }"
  >
    <time
      v-if="stamp"
      class="mindmate-collab-stamp__time"
      :datetime="createdAt"
    >
      {{ stamp }}
    </time>
    <span
      v-if="isOwn"
      class="mindmate-collab-stamp__mark"
      @mouseenter="showReaders"
      @mouseleave="hideReaders"
      @focusin="showReaders"
      @focusout="hideReaders"
    >
      <button
        type="button"
        class="mindmate-collab-stamp__checks"
        :class="`mindmate-collab-stamp__checks--${receipt}`"
        :aria-label="markLabel"
        :aria-expanded="open"
      >
        <svg
          v-if="receipt === 'sending'"
          viewBox="0 0 16 16"
          aria-hidden="true"
        >
          <circle
            cx="8"
            cy="8"
            r="5.25"
            fill="none"
            stroke="currentColor"
            stroke-width="1.4"
          />
          <path
            d="M8 5.2V8l2 1.4"
            fill="none"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
          />
        </svg>
        <svg
          v-else
          viewBox="0 0 18 16"
          aria-hidden="true"
        >
          <path
            d="M1.5 8.2 4.4 11 10 4.8"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <path
            v-if="receipt === 'read'"
            d="M6.2 8.2 9.1 11 14.8 4.8"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
      <div
        v-if="open"
        class="mindmate-collab-stamp__popover"
        role="tooltip"
      >
        <p class="mindmate-collab-stamp__popover-title">
          <I18nText
            v-if="readers.length"
            k="mindmate.collabReadBy"
          />
          <I18nText
            v-else-if="receipt === 'sending'"
            k="mindmate.collabSending"
          />
          <I18nText
            v-else
            k="mindmate.collabSent"
          />
        </p>
        <p
          v-if="receipt === 'sent'"
          class="mindmate-collab-stamp__popover-title"
        >
          <I18nText k="mindmate.collabReadNone" />
        </p>
        <ul v-if="readers.length">
          <li
            v-for="reader in readers"
            :key="reader.userId"
          >
            <span>{{ reader.username }}</span>
            <time
              v-if="formatCollabMessageStamp(reader.readAt)"
              :datetime="reader.readAt"
            >
              {{ formatCollabMessageStamp(reader.readAt) }}
            </time>
          </li>
        </ul>
      </div>
    </span>
  </div>
</template>

<style scoped>
.mindmate-collab-stamp {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  margin-top: 0.2rem;
  min-height: 1rem;
  color: #a8a29e;
  font-size: 11px;
  line-height: 1;
}

.mindmate-collab-stamp--own {
  flex-direction: row;
}

.mindmate-collab-stamp__mark {
  position: relative;
  display: inline-flex;
}

.mindmate-collab-stamp__checks {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15rem;
  height: 1rem;
  padding: 0;
  border: 0;
  background: transparent;
  color: #a8a29e;
  cursor: default;
}

.mindmate-collab-stamp__checks svg {
  width: 1.05rem;
  height: 0.9rem;
}

.mindmate-collab-stamp__checks--read {
  color: #38bdf8;
}

.mindmate-collab-stamp__popover {
  position: absolute;
  z-index: 20;
  right: 0;
  bottom: calc(100% + 0.35rem);
  min-width: 10rem;
  max-width: 16rem;
  padding: 0.5rem 0.65rem;
  border-radius: 0.65rem;
  background: #1c1917;
  color: #fafaf9;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.18);
  text-align: left;
}

.mindmate-collab-stamp__popover-title {
  margin: 0;
  font-size: 11px;
  color: #d6d3d1;
}

.mindmate-collab-stamp__popover ul {
  margin: 0.35rem 0 0;
  padding: 0;
  list-style: none;
}

.mindmate-collab-stamp__popover li {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.15rem 0;
  font-size: 12px;
}

.mindmate-collab-stamp__popover time {
  color: #a8a29e;
  white-space: nowrap;
}
</style>
