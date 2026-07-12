<script setup lang="ts">
/**
 * Scrollable chat transcript for MobileKittyPage — same bubble system as one-sentence modal.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { ElAvatar } from 'element-plus'

import OneSentenceKittyAvatar from '@/components/canvas/OneSentenceKittyAvatar.vue'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'
import type {
  OneSentenceChatMessage,
  OneSentenceClarifyChoice,
} from '@/stores/oneSentence'
import { resolveUserAvatarEmoji } from '@/utils/userAvatarEmoji'

const props = defineProps<{
  messages: OneSentenceChatMessage[]
}>()

const emit = defineEmits<{
  (e: 'select-choice', choice: OneSentenceClarifyChoice): void
  (e: 'bind-scroll', el: HTMLElement | null): void
}>()

const { t } = useLanguage()
const authStore = useAuthStore()
const scrollEl = ref<HTMLElement | null>(null)

const userAvatar = computed(() => resolveUserAvatarEmoji(authStore.user?.avatar))

function setScrollEl(el: unknown): void {
  const node = el instanceof HTMLElement ? el : null
  scrollEl.value = node
  emit('bind-scroll', node)
}

function scrollToBottom(): void {
  void nextTick(() => {
    const el = scrollEl.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

watch(
  () => props.messages.map((m) => `${m.id}:${m.text.length}:${m.streaming ? 1 : 0}`).join('|'),
  () => {
    scrollToBottom()
  }
)

onMounted(() => {
  scrollToBottom()
})
</script>

<template>
  <div
    :ref="setScrollEl"
    class="kitty-mobile-chat flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain px-1 py-2"
    role="log"
    aria-live="polite"
    :aria-label="t('mobile.kittyLive', 'Live conversation')"
  >
    <div
      v-for="msg in messages"
      :key="msg.id"
      class="kitty-mobile-chat__row flex w-full"
      :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
    >
      <div
        class="flex max-w-[92%] items-start gap-2"
        :class="msg.role === 'user' ? 'flex-row-reverse max-w-[88%]' : ''"
      >
        <OneSentenceKittyAvatar
          v-if="msg.role === 'kitty'"
          class="mt-0.5 shrink-0"
          :size="32"
        />
        <ElAvatar
          v-else
          :size="32"
          class="kitty-mobile-chat__user-avatar mt-0.5 shrink-0"
        >
          {{ userAvatar }}
        </ElAvatar>

        <div class="min-w-0 flex flex-col gap-1.5">
          <div
            class="kitty-mobile-chat__bubble rounded-2xl px-3 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words"
            :class="{
              'bg-violet-600 text-white rounded-br-md': msg.role === 'user',
              'bg-white text-slate-800 border border-slate-200/90 rounded-bl-md shadow-sm':
                msg.role === 'kitty',
              'opacity-80': msg.streaming,
              'opacity-70': msg.status === 'queued',
              'ring-1 ring-rose-300': msg.status === 'failed',
            }"
            :data-request-status="msg.status || undefined"
          >
            <p class="m-0">{{ msg.text }}</p>
            <p
              v-if="msg.role === 'user' && msg.status === 'queued'"
              class="mt-1 mb-0 text-[11px] opacity-80"
            >
              {{ t('canvas.mindMapOneSentence.requestQueued') }}
            </p>
            <p
              v-else-if="msg.role === 'user' && msg.status === 'failed'"
              class="mt-1 mb-0 text-[11px] text-rose-200"
            >
              {{ t('canvas.mindMapOneSentence.requestFailed') }}
            </p>
          </div>
          <div
            v-if="msg.choices?.length && !msg.choicesConsumed"
            class="flex flex-wrap gap-1.5"
            role="group"
            :aria-label="t('canvas.mindMapOneSentence.clarifyChoices')"
          >
            <button
              v-for="choice in msg.choices"
              :key="`${msg.id}-${choice.index}`"
              type="button"
              class="rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-xs font-medium text-violet-800 active:bg-violet-100"
              @click="emit('select-choice', choice)"
            >
              <span class="opacity-60 mr-1">{{ choice.index }}.</span>
              {{ choice.label }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kitty-mobile-chat__user-avatar {
  --el-avatar-bg-color: #fafafa;
  border: 2px solid #303133;
  font-size: 14px;
}
</style>
