<script setup lang="ts">
import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import type { ClipComment } from '@/utils/clipTeachingApi'

defineProps<{
  comments: ClipComment[]
  busy: boolean
}>()

const emit = defineEmits<{
  send: [payload: { body: string; parentId: number | null }]
  remove: [id: number]
}>()

const { t } = useLanguage()
const draft = ref('')
const replyTo = ref<number | null>(null)
const replyDraft = ref('')

function sendRoot(): void {
  const body = draft.value.trim()
  if (!body) return
  emit('send', { body, parentId: null })
  draft.value = ''
}

function sendReply(parentId: number): void {
  const body = replyDraft.value.trim()
  if (!body) return
  emit('send', { body, parentId })
  replyDraft.value = ''
  replyTo.value = null
}

function stamp(value: string | null): string {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}
</script>

<template>
  <section class="clip-comments">
    <h2><I18nText k="clipTeaching.commentsTitle" /></h2>
    <div class="clip-comments-compose">
      <textarea
        v-model="draft"
        rows="3"
        maxlength="2000"
        :placeholder="t('clipTeaching.commentPlaceholder')"
      />
      <button
        type="button"
        :disabled="busy || !draft.trim()"
        @click="sendRoot"
      >
        <I18nText k="clipTeaching.commentSend" />
      </button>
    </div>
    <p
      v-if="comments.length === 0"
      class="clip-comments-empty"
    >
      <I18nText k="clipTeaching.commentsEmpty" />
    </p>
    <article
      v-for="comment in comments"
      :key="comment.id"
      class="clip-comment"
    >
      <header>
        <strong
          ><template v-if="comment.author_name">{{ comment.author_name }}</template
          ><I18nText
            v-else
            k="clipTeaching.anonymous"
        /></strong>
        <time>{{ stamp(comment.created_at) }}</time>
      </header>
      <p>{{ comment.body }}</p>
      <div class="clip-comment-actions">
        <button
          type="button"
          @click="replyTo = replyTo === comment.id ? null : comment.id"
        >
          <I18nText k="clipTeaching.reply" />
        </button>
        <button
          v-if="comment.can_delete"
          type="button"
          @click="emit('remove', comment.id)"
        >
          <I18nText k="clipTeaching.deleteComment" />
        </button>
      </div>
      <div
        v-if="replyTo === comment.id"
        class="clip-comments-compose"
      >
        <textarea
          v-model="replyDraft"
          rows="2"
          maxlength="2000"
          :placeholder="t('clipTeaching.replyPlaceholder')"
        />
        <button
          type="button"
          :disabled="busy || !replyDraft.trim()"
          @click="sendReply(comment.id)"
        >
          <I18nText k="clipTeaching.commentSend" />
        </button>
      </div>
      <article
        v-for="reply in comment.replies"
        :key="reply.id"
        class="clip-comment clip-comment-reply"
      >
        <header>
          <strong
            ><template v-if="reply.author_name">{{ reply.author_name }}</template
            ><I18nText
              v-else
              k="clipTeaching.anonymous"
          /></strong>
          <time>{{ stamp(reply.created_at) }}</time>
        </header>
        <p>{{ reply.body }}</p>
        <button
          v-if="reply.can_delete"
          type="button"
          @click="emit('remove', reply.id)"
        >
          <I18nText k="clipTeaching.deleteComment" />
        </button>
      </article>
    </article>
  </section>
</template>

<style scoped>
.clip-comments h2 {
  margin: 0 0 8px;
  font-size: 16px;
}

.clip-comments-compose {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.clip-comments textarea {
  width: 100%;
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  padding: 8px;
  resize: vertical;
}

.clip-comments button {
  border: 1px solid #d6d3d1;
  border-radius: 8px;
  background: #fff;
  padding: 6px 10px;
  cursor: pointer;
}

.clip-comment {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e7e5e4;
}

.clip-comment header {
  display: flex;
  gap: 8px;
  color: #57534e;
  font-size: 13px;
}

.clip-comment p {
  margin: 6px 0;
  white-space: pre-wrap;
}

.clip-comment-reply {
  margin-left: 24px;
}

.clip-comments-empty {
  color: #78716c;
}
</style>
